# HomeMind

HomeMind is an experimental **agentic smart-home assistant** built around a small, locally hosted language model.

## Planned capabilities

- Understand natural-language home automation requests and simulated device states.
- Select and execute smart-home tools through a stateful agentic workflow.
- Handle multi-step requests, clarification, and tool failures.
- Evaluate a pretrained model against a fine-tuned version using LoRA.

## Technology

- **LLM:** Qwen3-1.7B
- **Inference:** Ollama
- **Orchestration:** LangChain and LangGraph
- **Fine-tuning:** Keras / LoRA (planned)
- **Environment:** Python and simulated smart-home devices

## Status

Early development. The first step is baseline inference with Qwen3-1.7B through Ollama and LangChain. Source code will be added incrementally under `src/`.
