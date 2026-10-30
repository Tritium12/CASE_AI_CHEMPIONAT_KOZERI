import os
import sys
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.documents import Document

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================


def get_db_path():
    return "./chroma_db"

CHROMA_DB_DIR = get_db_path()
COLLECTION_NAME = "my_docs"
EMBEDDING_MODEL = "bge-m3"
LLM_MODEL = "qwen2.5"

# Глобальная переменная, чтобы цепочка создавалась только один раз при первом запросе
_rag_chain_instance = None

# Глобальный список для сбора ссылок (очищается перед каждым запросом)
CURRENT_SOURCES = []


def format_docs(docs):
    global CURRENT_SOURCES
    CURRENT_SOURCES = []  # Очищаем перед новым запросом

    formatted = []
    for i, doc in enumerate(docs):
        # Сохраняем ссылку в глобальный список
        source = doc.metadata.get('source', 'Неизвестный источник')
        if source not in CURRENT_SOURCES:
            CURRENT_SOURCES.append(source)

        # formatted.append(f"[{i+1}] Источник: {source}\nТекст: {doc.page_content}")
    return "\n\n".join(formatted)


def _init_rag_chain():
    """Инициализирует все модели и цепочку. Вызывается один раз."""

    # Подключаем эмбеддинги и базу
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )

    # ==========================================
    # 2. РЕТРИВЕР (ГИБРИДНЫЙ ПОИСК + РЕРАНКИНГ)
    # ==========================================

    # А) Векторный поиск (по смыслу)
    vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    # Б) Поиск по ключевым словам (BM25)
    all_docs_data = vectorstore.get()
    all_docs = [Document(page_content=text, metadata=meta) for text, meta in
                zip(all_docs_data['documents'], all_docs_data['metadatas'])]

    # Защита от пустой базы
    if not all_docs:
        raise ValueError("В базе данных нет документов! Запусти сначала ingest.py")

    bm25_retriever = BM25Retriever.from_documents(all_docs)
    bm25_retriever.k = 5

    # В) Объединяем (Векторы + Слова) - Гибридный поиск
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.5, 0.5]
    )

    # Г) Реранкинг (Судья)
    cross_encoder = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
    compressor = CrossEncoderReranker(model=cross_encoder, top_n=3)  # Оставляем топ-3

    final_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=ensemble_retriever
    )

    # ==========================================
    # 3. ПРОМПТ-ИНЖИНИРИНГ
    # ==========================================
    llm = ChatOllama(model=LLM_MODEL, temperature=0)

    # Жесткие правила для LLM
    system_prompt = (
        "Ты — полезный ассистент для абитуриентов МГТУ им. Баумана. Твоя задача — отвечать на вопросы, опираясь на базу данных.\n"
        "Если есть информация, которая позволяет ответить на вопрос (даже если она изложена другими словами или разбита на части), обязательно сформулируй ответ.\n"
        "Только если СОВСЕМ нет никаких фактов по теме вопроса, скажи: 'Я не знаю ответа на этот вопрос'.\n"
        "После каждого факта в тексте ставь сноску на источник в формате [1], [2] и т.д.\n"
        "В конце ответа выведи список использованных источников в формате: [1] ссылка_на_источник.\n\n"
        "Контекст:\n{context}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}"),
    ])

    # ==========================================
    # 4. ОРКЕСТРАЦИЯ (Сборка конвейера)
    # ==========================================
    chain = (
            {"context": final_retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
    )

    return chain


def ask_rag(question: str):
    global _rag_chain_instance
    global CURRENT_SOURCES

    if _rag_chain_instance is None:
        _rag_chain_instance = _init_rag_chain()

    # Очищаем ссылки перед запуском
    CURRENT_SOURCES = []

    # Запускаем цепочку (она вызовет format_docs, который наполнит CURRENT_SOURCES)
    answer = _rag_chain_instance.invoke(question)

    # Возвращаем ответ и список ссылок
    return answer, CURRENT_SOURCES