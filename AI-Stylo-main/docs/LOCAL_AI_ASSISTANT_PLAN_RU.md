# Локальный AI-ассистент для Сергея (Ollama-first) — план реализации

## 1) Цель и область применения

**Общая цель:** построить полностью локального AI-ассистента (offline-first) для генерации креативных материалов в двух доменах:

- **Fashion:** descriptions коллекций, moodboards, стилистические правила, prompt-идеи для визуализации.
- **Cinema / Video:** логлайны, тритменты, shot-листы, prompt-pack для генерации видео.

Ключевой результат: единая система, где LLM-вычисления выполняются локально через **Ollama**, а UI предоставляет удобный рабочий интерфейс для ежедневного creative-пайплайна.

## 2) Нефункциональные требования и ограничения

- **Полная автономность:** никаких внешних LLM API; все генерации идут через локальный Ollama.
- **Единый LLM-доступ:** коммуникация с моделью концентрируется в `OllamaAdapter` и общем интерфейсе клиента.
- **Инструментальные вызовы (tools):** поддержка структурированных вызовов функций (`make_shotlist`, `make_prompt_pack`, `make_fashion_capsule`, `save_preference`) с JSON-ответами.
- **Конфигурируемость:** база URL, модели и параметры генерации читаются из `.env`/YAML-профиля.
- **Контракты данных:** все результаты нормализуются в структуры `contracts.py` (например, `Profile`, `AssistantResult`).
- **Память:** локальное хранение профиля/предпочтений/заметок через SQLite; опциональный векторный слой для RAG.
- **Эволюция и рефлексия:** после сессии фиксируется краткая заметка (reflect), чтобы система лучше персонализировалась со временем.

## 3) Целевая архитектура

```text
User -> Streamlit UI -> PEAROrchestrator
                       |-> MemoryDB (SQLite + optional vectors)
                       |-> Tools Registry (shotlist/prompt-pack/fashion)
                       |-> OllamaAdapter -> Local Ollama Server (11434)
```

### Компоненты

- **UI (Streamlit):** ввод запроса, выбор домена (fashion/cinema), показ ответа, инструментальных результатов и заметок.
- **Orchestrator (PEAR-loop):**
  - классификация домена;
  - сбор контекста (профиль + предпочтения + память);
  - формирование system prompt;
  - вызов Ollama;
  - обработка tool-calling;
  - запись событий и reflect-note.
- **MemoryDB:**
  - `profile_store` — профиль пользователя;
  - `preference_store` — явные предпочтения;
  - `vector_store` — семантический поиск (опционально).
- **Tools registry:** pure-функции, возвращающие JSON по контракту.
- **OllamaAdapter:** `chat`, `chat_stream`, `embed`, `health`/`list_models`.

## 4) Инвентаризация модулей и соответствие

| Модуль | Файл/папка | Назначение |
|---|---|---|
| Orchestrator | `apps/core/ai/orchestrator.py` | PEAR-цикл, координация prompt/tools/memory |
| Ollama Adapter | `apps/adapters/ollama_adapter.py` | локальный HTTP-клиент Ollama |
| Tools | `apps/core/tools/registry.py` | генерация shotlist/prompt-pack/fashion + save_preference |
| Memory | `apps/core/memory/*` | SQLite-хранилища профиля/предпочтений/векторов |
| Skills Engine | `apps/core/skills_engine.py` | прогресс, навыки и геймификация |
| UI | `apps/web/streamlit_*` | пользовательские режимы работы |
| Config | `configs/sergii_profile.yaml` | профиль и значения по умолчанию |

> Примечание: таблица описывает целевую структуру и может внедряться поэтапно без «большого взрыва».

## 5) Пошаговый план интеграции

1. **Развернуть Ollama локально**
   - docker-контейнер или локальная установка;
   - загрузить базовую модель (например, `mistral:7b`/`llama3`).
2. **Подготовить Python окружение**
   - установить зависимости;
   - зафиксировать версии в `requirements.txt`.
3. **Собрать LLM-слой**
   - добавить `OllamaAdapter`;
   - ввести `health-check` до старта UI/оркестратора.
4. **Реализовать PEAROrchestrator**
   - доменная классификация;
   - диалог + инструментальные вызовы;
   - reflect-постобработка.
5. **Собрать слой памяти**
   - SQLite таблицы и хранилища;
   - bootstrap профиля из YAML.
6. **Интегрировать Streamlit UI**
   - общий экран генерации;
   - вывод tool-результатов и сохранённых предпочтений.
7. **Покрыть тестами и CI**
   - unit + integration + basic E2E;
   - пайплайн с автопроверками.

## 6) Дорожная карта (майлстоуны)

| Milestone | Содержание | Срок |
|---|---|---|
| M1: Environment | Python/Docker/Ollama, зависимости, baseline run | 1 неделя |
| M2: Core PEAR | базовый Orchestrator + Ollama chat | 2 недели |
| M3: Tools | JSON tools + dispatch + save_preference | 2 недели |
| M4: UI + Memory | Streamlit-экран, SQLite stores, bootstrap profile | 2 недели |
| M5: QA + CI/CD | unit/integration/E2E smoke + GitHub Actions | 2 недели |
| M6: Hardening | рефакторинг, docs, обработка edge-cases | 1 неделя |

## 7) Риски и меры

- **Низкая производительность железа** → старт с лёгких моделей, профилирование, кэширование.
- **Сложность интеграции зависимостей** → pin версий, контейнеризация среды.
- **Нестабильность LLM-ответов** → строгие контракты JSON + fallback-ветки + тесты эталонных сценариев.
- **Сдвиг сроков UI** → приоритизация core-потока (prompt -> response -> memory).

## 8) План тестирования и приёмки

### Unit
- tools: корректность JSON-структур и обязательных полей;
- memory stores: CRUD и миграции;
- adapter: сериализация/десериализация и error-path.

### Integration
- orchestrator + mocked ollama adapter;
- сценарий tool-calling и запись preference.

### E2E (локально)
- поднять сервисы, выполнить fashion и cinema запросы;
- проверить: корректность ответа, отсутствие network-зависимости для LLM, стабильность UI.

**Критерии приёмки:**
- core-сценарии выполняются «из коробки»;
- инструменты отдают валидный JSON;
- состояние пользователя сохраняется между сессиями;
- система работоспособна в offline-first режиме.

## 9) Оценка усилий и бюджет (черновая)

Оценка: **~520 часов** суммарно, бюджет порядка **$28k–31k** (с contingency ~20%).

| Роль | Ставка | Часы | Стоимость |
|---|---:|---:|---:|
| PM | $60/h | 50 | $3,000 |
| Dev | $55/h | 350 | $19,250 |
| QA | $50/h | 120 | $6,000 |
| **Итого** |  | **520** | **$28,250** |

## 10) Рекомендации для старта в текущем репозитории

1. Создать ветку `feature/ollama-local-core`.
2. Добавить базовые файлы:
   - `apps/adapters/ollama_adapter.py`
   - `apps/core/ai/orchestrator.py`
   - `apps/core/tools/registry.py`
   - `apps/core/memory/{profile_store.py,preference_store.py,vector_store.py}`
   - `configs/sergii_profile.yaml`
3. Сначала закрыть `health + chat + 1 tool + sqlite preference` как минимально работающий vertical slice.
4. После этого расширять tools и UI.

---

Документ фиксирует единое видение архитектуры и поэтапной интеграции offline LLM-системы на базе Ollama для задач fashion/video.

## 11) Верификация статуса и отметка EvoPyramid

Актуальный статус реализации по репозиторию вынесен в `docs/IMPLEMENTATION_STATUS_RU.md`.

Работа и тестирование ведутся на базе **EvoPyramid architecture for AI** в формате минимально необходимой интеграции (модульность + PEAR-цикл + рефлексия + проверяемость контрактами).

