"""Gradio Blocks app for the AI Project RAG chatbot.

Phase 1 + Phase 2. Run with::

    From the repository root, run ``python -m webui_launcher`` after setting
    ``PYTHONPATH=src`` (or use the Docker Compose command).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import gradio as gr

THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag_chat_v2 import initialize_pipeline  # noqa: E402

from webui.polish_llm import load_polish_llm  # noqa: E402

from webui.chat_handler import chat_turn, format_sources_markdown  # noqa: E402
from webui.hybrid_pipeline import route_through_hybrid  # noqa: E402
from webui.config import (  # noqa: E402
    ALLOWED_UPLOAD_EXTS,
    DEFAULT_DISPLAY_THRESHOLD,
    DEFAULT_TOP_K,
    EXAMPLE_QUESTIONS,
    WEBUI_HOST,
    WEBUI_PORT,
    WEBUI_TITLE,
    upload_policy_text,
)
from webui.document_processor import (  # noqa: E402
    attach_documents,
    chunk_text,
    parse_file,
    process_uploads,
    remove_uploaded_document,
)
from webui.export import to_json, to_markdown, save_to_disk  # noqa: E402
from webui.config import LOGS_DIR  # noqa: E402
from webui.feedback_log import log_feedback  # noqa: E402

_LOGGER = logging.getLogger(__name__)


def _build_welcome_html() -> str:
    """Friendly empty-state panel shown above the chat on first load."""
    return (
        "<div style='padding:16px;border-radius:10px;"
        "background:#0d1117;border:1px solid #30363d;"
        "font-family:system-ui;color:#c9d1d9;'>"
        "<div style='font-size:15px;font-weight:600;margin-bottom:8px;'>"
        "Ask anything the knowledge base can answer</div>"
        "<div style='font-size:13px;color:#8b949e;line-height:1.5;'>"
        "This is a self-hosted question-answering system. It retrieves "
        "relevant passages from a local knowledge base, validates that the "
        "question is meaningful, and synthesizes an answer with citations."
        "</div>"
        "<div style='font-size:12px;color:#6e7681;margin-top:8px;'>"
        "Tip: try the example questions below to see what it does, or "
        "upload your own documents in the Documents tab to extend the "
        "knowledge base."
        "</div>"
        "</div>"
    )


def _confidence_badge(confidence, threshold: float) -> str:
    """Color-coded HTML badge for the answer detail panel."""
    if confidence is None:
        color = "#888"
        text = "n/a"
    elif confidence >= max(threshold, 0.7):
        color = "#3fb950"
        text = f"{confidence:.2f}"
    elif confidence >= threshold:
        color = "#d29922"
        text = f"{confidence:.2f}"
    else:
        color = "#f85149"
        text = f"{confidence:.2f}"
    return (
        f"<div style='display:inline-block;padding:6px 12px;"
        f"border-radius:8px;background:{color}22;color:{color};"
        f"border:1px solid {color};font-weight:600;'>"
        f"Confidence: {text}</div>"
    )


def _build_header_html(status: dict) -> str:
    return (
        f"<div style='display:flex;gap:24px;align-items:center;"
        f"padding:8px 0;font-family:system-ui;'>"
        f"<div style='font-size:20px;font-weight:700;'>"
        f"{WEBUI_TITLE}</div>"
        f"<div style='color:#888;font-size:13px;'>"
        f"Device: <b>{status['device']}</b> &middot; "
        f"Chunks: <b>{status['chunks']:,}</b> &middot; "
        f"Model: <b>{status['model']}</b>"
        f"</div>"
        f"</div>"
    )


def _format_kb_table(uploaded_docs: list[dict]) -> list[list]:
    rows = []
    for d in uploaded_docs:
        rows.append([
            d.get("document_name", ""),
            d.get("extension", ""),
            d.get("chunk_count", 0),
            d.get("document_id", ""),
        ])
    return rows


def _document_choices(uploaded_docs: list[dict]) -> list[str]:
    return [
        str(d.get("document_id"))
        for d in uploaded_docs
        if d.get("document_id")
    ]


def respond(
    user_message: str,
    history: list,
    top_k: int,
    threshold: float,
    pipeline: dict,
    polish_llm_state,
    scope_document_id: str | None = None,
):
    """Gradio callback: process one user message, append to history.

    Uses ``route_through_hybrid`` so the polish LLM (Qwen2.5-1.5B)
    handles generative and hybrid cases, while the existing
    rag_chat_v2 path handles simple lookups.

    Returns a tuple of 12 values that align with the order of
    ``chat_outputs`` in ``build_demo``: history, cleared input, meta,
    sources JSON, raw answer, last question, plus the per-turn fields
    the feedback buttons need (last_intent, last_answer_type,
    last_confidence, last_supported, last_sources_json) and a feedback
    status string.
    """
    if history is None:
        history = []

    if not user_message or not user_message.strip():
        empty_sources = "[]"
        feedback_clear = "Click 👍 or 👎 to rate the last answer."
        return (
            history, "", "", empty_sources, "", "", "",
            "", "", "", empty_sources, feedback_clear,
        )

    turn = route_through_hybrid(
        pipeline,
        user_message,
        polish_llm_state,
        top_k=top_k,
        document_ids=(
            [scope_document_id]
            if scope_document_id and scope_document_id != "All documents"
            else None
        ),
    )
    answer = turn.answer or ""

    bubble = answer + format_sources_markdown(turn.sources)

    history = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": bubble},
    ]

    confidence_html = _confidence_badge(turn.confidence, threshold)
    supported_text = "Yes" if turn.supported else "No"
    sources_json = json.dumps(turn.sources, indent=2)

    mode_label = {
        "rag_only": "RAG only (small model)",
        "polish_lookup": "RAG + Qwen polish",
        "polish_generative": "Qwen generative",
        "polish_hybrid": "RAG + Qwen hybrid",
        "empty": "empty input",
        "error": "error",
    }.get(turn.mode, turn.mode)

    meta_md = (
        f"**Intent:** `{turn.intent}`  \n"
        f"**Answer type:** `{turn.answer_type}`  \n"
        f"**Mode:** `{mode_label}`  \n"
        f"**Supported:** {supported_text}  \n"
        f"{confidence_html}"
    )

    feedback_prompt = (
        "Was this answer helpful? Click 👍 or 👎 to record feedback."
    )

    return (
        history,
        "",
        meta_md,
        sources_json,
        answer,
        user_message,
        turn.intent or "",
        turn.answer_type or "",
        float(turn.confidence) if isinstance(turn.confidence, (int, float)) else None,
        bool(turn.supported),
        sources_json,
        feedback_prompt,
    )


def clear_history():
    """Reset chat, detail panel, and feedback state."""
    feedback_clear = "Click 👍 or 👎 to rate the last answer."
    return (
        [], "", "", "[]", "", "",
        "", "", None, False, "[]", feedback_clear,
    )


def record_feedback(
    vote: int,
    last_question: str,
    last_answer: str,
    last_intent: str,
    last_answer_type: str,
    last_confidence,
    last_supported,
    last_sources_json: str,
):
    """Persist a thumbs up/down vote for the last assistant answer.

    Parameters come from Gradio ``gr.State`` boxes updated by
    ``respond``. Returns a status string rendered in the feedback slot.
    """
    if not last_question or not last_answer:
        return "No answer to rate yet — ask a question first."

    # last_sources_json is a string for round-tripping through Gradio
    # State; we want a list of dicts for the log row.
    sources: list[dict] = []
    if last_sources_json:
        try:
            parsed = json.loads(last_sources_json)
            if isinstance(parsed, list):
                sources = parsed
        except (TypeError, ValueError):
            sources = []

    try:
        path = log_feedback(
            int(vote),
            question=last_question,
            answer=last_answer,
            intent=last_intent or "",
            answer_type=last_answer_type or "",
            confidence=last_confidence,
            supported=bool(last_supported) if last_supported is not None else None,
            sources=sources,
        )
    except Exception:
        return "⚠️ Feedback could not be recorded. Please try again."

    label = "👍 up" if vote > 0 else "👎 down" if vote < 0 else "neutral"
    return f"Recorded {label} for \"{last_question[:60]}\" → `{path.name}`"


def handle_uploads(files, pipeline: dict):
    """Process uploaded files, attach to pipeline, refresh KB table.

    Returns (status_md, kb_rows, header_html).
    """
    if not files:
        return (
            f"No files uploaded yet. Pick one or more supported files. "
            f"{upload_policy_text()}",
            [],
            _build_header_html(_status_from_pipeline(pipeline)),
        )

    file_paths = [f.name if hasattr(f, "name") else f for f in files]
    parsed, errors = process_uploads(pipeline, file_paths)

    msg_lines = []
    if parsed:
        try:
            added = attach_documents(pipeline, parsed)
        except ValueError as exc:
            msg_lines.append(f"Upload rejected: {exc}")
        else:
            msg_lines.append(
                f"Indexed {added} new chunks from {len(parsed)} file(s)."
            )
    if errors:
        msg_lines.append("Errors:")
        msg_lines.extend(f"- {e}" for e in errors)
    status_md = "\n".join(msg_lines) if msg_lines else "No changes."

    return (
        status_md,
        _format_kb_table(pipeline.get("uploaded_docs", [])),
        _build_header_html(_status_from_pipeline(pipeline)),
    )


def _status_from_pipeline(pipeline: dict) -> dict:
    return {
        "device": pipeline.get("device", "?"),
        "chunks": len(pipeline.get("chunks", []) or []),
        "model": pipeline.get("model_name", "reasoning_model_v1"),
    }


def export_conversation(history: list, fmt: str):
    """Render the current history as JSON or Markdown and save to disk."""
    if not history:
        return "*Nothing to export yet.*", None
    if fmt == "json":
        content = to_json(history)
        path = save_to_disk(content, LOGS_DIR / "exports", "chat", "json")
        return f"Saved JSON export `{path.name}`.", str(path)
    if fmt == "markdown":
        content = to_markdown(history)
        path = save_to_disk(content, LOGS_DIR / "exports", "chat", "md")
        return f"Saved Markdown export `{path.name}`.", str(path)
    return "Unknown export format.", None


def build_demo(pipeline: dict, polish_llm=None):
    status = _status_from_pipeline(pipeline)

    with gr.Blocks(title=WEBUI_TITLE, theme=gr.themes.Soft(), css=".gradio-container { max-width: 1200px !important; }") as demo:
        # Header with system status. Stays static for now; future work
        # could refresh it after each turn to show live counts.
        gr.HTML(_build_header_html(status))

        with gr.Tabs():
            # ============== Chat tab ==============
            with gr.Tab("Chat"):
                with gr.Row():
                    with gr.Column(scale=3):
                        gr.HTML(_build_welcome_html())
                        chatbot = gr.Chatbot(
                            label="Conversation",
                            height=520,
                            type="messages",
                        )
                        with gr.Row():
                            msg = gr.Textbox(
                                label="Your question",
                                placeholder=(
                                    "e.g. Why did the Roman Empire decline?"
                                ),
                                scale=5,
                                autofocus=True,
                                show_copy_button=True,
                            )
                            send_btn = gr.Button(
                                "Send", scale=1, variant="primary"
                            )
                        with gr.Row():
                            clear_btn = gr.Button(
                                "Clear conversation", variant="stop"
                            )

                    with gr.Column(scale=2):
                        with gr.Accordion("Answer details", open=True):
                            meta_md = gr.Markdown("*No answer yet.*")
                            answer_box = gr.Textbox(
                                label="Raw answer",
                                lines=4,
                                interactive=False,
                                show_copy_button=True,
                            )
                            sources_box = gr.Textbox(
                                label="Sources (JSON, for debugging)",
                                lines=8,
                                interactive=False,
                                show_copy_button=True,
                            )
                        with gr.Accordion("Settings", open=False):
                            top_k = gr.Slider(
                                minimum=1, maximum=10, step=1,
                                value=DEFAULT_TOP_K,
                                label="Top-K retrieved chunks",
                            )
                            threshold = gr.Slider(
                                minimum=0.0, maximum=1.0, step=0.05,
                                value=DEFAULT_DISPLAY_THRESHOLD,
                                label="Confidence highlight threshold",
                            )
                            scope_selector = gr.Dropdown(
                                choices=["All documents"] + _document_choices(
                                    pipeline.get("uploaded_docs", [])
                                ),
                                value="All documents",
                                label="Scope to document",
                                interactive=True,
                            )
                        last_question_box = gr.Textbox(
                            label="Last question",
                            interactive=False,
                            visible=False,
                        )

                def _respond_server(message, history, top_k_value, threshold_value, scope_value):
                    selected_id = None
                    if scope_value and scope_value != "All documents":
                        selected_id = scope_value
                    return respond(
                        message,
                        history,
                        top_k_value,
                        threshold_value,
                        pipeline,
                        polish_llm,
                        scope_document_id=selected_id,
                    )

                chat_inputs = [msg, chatbot, top_k, threshold, scope_selector]
                # Per-turn state used by the feedback buttons.
                last_intent_box = gr.State("")
                last_answer_type_box = gr.State("")
                last_confidence_box = gr.State(None)
                last_supported_box = gr.State(False)
                last_sources_box = gr.State("[]")
                feedback_status = gr.Markdown(
                    "Click 👍 or 👎 to rate the last answer."
                )

                chat_outputs = [
                    chatbot, msg, meta_md, sources_box,
                    answer_box, last_question_box,
                    last_intent_box, last_answer_type_box,
                    last_confidence_box, last_supported_box,
                    last_sources_box, feedback_status,
                ]
                send_btn.click(
                    _respond_server, inputs=chat_inputs, outputs=chat_outputs,
                    api_name="chat",
                )
                msg.submit(
                    _respond_server, inputs=chat_inputs, outputs=chat_outputs,
                )
                clear_btn.click(
                    clear_history, outputs=chat_outputs,
                )

                # Feedback row — only visible once there is an answer.
                with gr.Row():
                    up_btn = gr.Button("👍 Helpful", scale=1)
                    down_btn = gr.Button("👎 Not helpful", scale=1)

                feedback_inputs = [
                    gr.State(1),          # vote value
                    last_question_box,
                    answer_box,
                    last_intent_box,
                    last_answer_type_box,
                    last_confidence_box,
                    last_supported_box,
                    last_sources_box,
                ]
                up_btn.click(
                    record_feedback,
                    inputs=feedback_inputs,
                    outputs=[feedback_status],
                )
                down_inputs = [gr.State(-1)] + feedback_inputs[1:]
                down_btn.click(
                    record_feedback,
                    inputs=down_inputs,
                    outputs=[feedback_status],
                )

            # ============== Documents tab ==============
            with gr.Tab("Documents"):
                gr.Markdown(
                    "Upload PDF, DOCX, or TXT files to extend the "
                    "knowledge base. Files are chunked and merged into "
                    "the live retrieval index without restarting.\n\n"
                    f"{upload_policy_text()}"
                )
                upload = gr.File(
                    label="Upload documents",
                    file_count="multiple",
                    file_types=[ext for ext in ALLOWED_UPLOAD_EXTS],
                )
                upload_btn = gr.Button("Index uploads", variant="primary")
                upload_status = gr.Markdown(
                    "No files uploaded yet."
                )
                kb_table = gr.Dataframe(
                    headers=["Name", "Type", "Chunks", "Document ID"],
                    value=_format_kb_table(pipeline.get("uploaded_docs", [])),
                    label="Knowledge base (uploaded docs)",
                    interactive=False,
                )
                with gr.Row():
                    document_selector = gr.Dropdown(
                        choices=_document_choices(pipeline.get("uploaded_docs", [])),
                        label="Document ID to delete",
                        interactive=True,
                    )
                    delete_btn = gr.Button("Delete document", variant="stop")
                delete_status = gr.Markdown("")

                def _handle_uploads_server(files):
                    status_md, rows, _header_html = handle_uploads(files, pipeline)
                    updated_choices = ["All documents"] + _document_choices(
                        pipeline.get("uploaded_docs", [])
                    )
                    return status_md, rows, gr.update(
                        choices=_document_choices(pipeline.get("uploaded_docs", []))
                    ), gr.update(choices=updated_choices)

                upload_btn.click(
                    _handle_uploads_server,
                    inputs=[upload],
                    outputs=[upload_status, kb_table, document_selector, scope_selector],
                )

                def _delete_document_server(document_id):
                    updated_choices = ["All documents"] + _document_choices(
                        pipeline.get("uploaded_docs", [])
                    )
                    scope_update = gr.update(choices=updated_choices, value="All documents")
                    if not document_id:
                        return "Select a document ID first.", _format_kb_table(
                            pipeline.get("uploaded_docs", [])
                        ), gr.update(
                            choices=_document_choices(pipeline.get("uploaded_docs", []))
                        ), None, scope_update
                    removed = remove_uploaded_document(pipeline, str(document_id))
                    if removed == 0:
                        return "Document not found.", _format_kb_table(
                            pipeline.get("uploaded_docs", [])
                        ), gr.update(
                            choices=_document_choices(pipeline.get("uploaded_docs", []))
                        ), None, scope_update
                    return (
                        f"Deleted document `{document_id}` ({removed} chunks removed).",
                        _format_kb_table(pipeline.get("uploaded_docs", [])),
                        gr.update(
                            choices=_document_choices(pipeline.get("uploaded_docs", []))
                        ),
                        None,
                        scope_update,
                    )

                delete_btn.click(
                    _delete_document_server,
                    inputs=[document_selector],
                    outputs=[delete_status, kb_table, document_selector, document_selector, scope_selector],
                )

            # ============== Export tab ==============
            with gr.Tab("Export"):
                gr.Markdown(
                    "Save the current conversation as JSON or Markdown. "
                    f"Files land in the `logs/exports/` directory."
                )
                fmt_radio = gr.Radio(
                    choices=["markdown", "json"],
                    value="markdown",
                    label="Format",
                )
                export_btn = gr.Button("Export now", variant="primary")
                export_status = gr.Markdown("*No export yet.*")
                # Hidden state mirroring chatbot so we can grab the history
                export_history_state = gr.State(value=[])

                def _do_export(history, fmt):
                    return export_conversation(history, fmt)

                export_btn.click(
                    _do_export,
                    inputs=[chatbot, fmt_radio],
                    outputs=[export_status, gr.File(visible=False)],
                )

    return demo


def main():
    _LOGGER.info("Initializing pipeline")
    pipeline = initialize_pipeline(verbose=True)
    pipeline["model_name"] = "reasoning_model_v1"
    pipeline.setdefault("uploaded_docs", [])

    polish_llm = None
    try:
        _LOGGER.info("Loading polish LLM (Qwen2.5-1.5B-Instruct)")
        polish_llm = load_polish_llm()
        _LOGGER.info(
            "Polish LLM ready on %s (%s)",
            polish_llm.device,
            polish_llm.model_name,
        )
    except FileNotFoundError:
        _LOGGER.warning("Optional polish LLM not available; using core answers.")
    except Exception:
        _LOGGER.warning("Optional polish LLM failed to load; using core answers.")

    _LOGGER.info("Pipeline ready. Launching Gradio UI")

    demo = build_demo(pipeline, polish_llm=polish_llm)
    demo.queue(default_concurrency_limit=4).launch(
        server_name=WEBUI_HOST,
        server_port=WEBUI_PORT,
        show_error=False,
        inbrowser=False,
        share=False,
    )


if __name__ == "__main__":
    main()
