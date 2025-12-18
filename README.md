<div align="center">
  <img src="docs/assets/sentio_logo.svg" alt="Animated Sentio Engine Logo" width="800"/>
  <h1>Sentio Engine</h1>
  <p>A Self-Sufficient Emotional Engine for Advanced AI</p>

  ---
  > **Note:** This project is a prototype/sample and is currently under development (temporarily frozen). It has not been fully tested for production use.
  ---

  <p>
    <img src="https://img.shields.io/badge/Project%20Status-Prototype-orange" alt="Project Status: Prototype"/>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/>
    <img src="https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white" alt="Python Version"/>
    <img src="https://img.shields.io/badge/Framework-FastAPI-009688.svg?logo=fastapi" alt="Framework: FastAPI"/>
    <img src="https://img.shields.io/badge/API-Protobuf-blue" alt="API: Protobuf"/>
  </p>
</div>

---

## Table of Contents
- [Why Sentio Engine?](#why-sentio-engine)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Real-World Use Cases](#real-world-use-cases)
- [Installation](#installation)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [Full Documentation](#full-documentation)

## Why Sentio Engine?

While many AI systems can process language, few can grasp its emotional context. Sentio Engine addresses this gap by providing a **dedicated, stateful microservice for emotional simulation**.

*   **Go Beyond Stateless Sentiment:** Instead of simple, one-off sentiment analysis, Sentio provides a persistent emotional state that evolves over time, giving your AI a consistent personality and memory.
*   **Decoupled by Design:** As a standalone service, it can be integrated into any AI application, regardless of the primary programming language. It won't bloat your main application's logic.
*   **High Performance:** Built with FastAPI and Protobuf, the engine is designed for low-latency communication, ensuring it won't be a bottleneck.
*   **Deeply Customizable:** The AI's "personality"—its baseline moods, emotional responses, and core drives—is defined in simple JSON files, not code.

## Key Features

- **Stateful Emotional Core:** Maintains an in-memory emotional state that reacts to stimuli and decays naturally over time.
- **Protobuf API:** Uses a high-performance, language-agnostic Protocol Buffers API for communication (`POST /stimulus`, `GET /report`).
- **Configurable Personality:** Define the AI's emotional palette, baseline moods, and decay rates in simple `.json` files.
- **Long-Term Memory:** Logs significant emotional events to a MongoDB database, creating a history of the AI's "life experiences."
- **Modern Python Stack:** Built with Poetry, FastAPI, and Motor, following modern development best practices.

## Architecture

The engine operates as a decoupled microservice, separating emotional processing from the main logic of your AI application.

```mermaid
graph LR
    subgraph External Systems
        direction LR
        A[LLM Parser] -- Protobuf --> B{Sentio Engine API};
        B -- Protobuf --> C[LLM Generator];
    end

    subgraph Sentio Engine Service
        direction TB
        B -- HTTP Request --> D[FastAPI Server];
        D -- Calls --> E[Core Engine];
        E -- Reads --> F["Personality Configs (.json)"];
        E -- "Reads/Writes" --> G[(MongoDB Database)];
    end

    style A fill:#cce5ff,stroke:#333
    style C fill:#cce5ff,stroke:#333
    style B fill:#f9f,stroke:#333,stroke-width:2px
    style E fill:#ccffcc,stroke:#333
```

1.  **LLM Parser:** An external component analyzes user input and translates it into a `Stimulus` message.
2.  **Sentio Engine API:** Receives the `Stimulus`, passes it to the Core Engine, and stores emotional changes in the database.
3.  **LLM Generator:** Before generating a response, it requests a `Report` from the engine and injects the AI's current emotional state into its system prompt.

## Real-World Use Cases

#### Use Case 1: Empathetic Companion AI

An AI companion can use Sentio to develop a consistent personality and emotional memory.
- **Workflow:** A user tells the AI, "I'm so happy, I got a new job!"
- **Execution:**
    1.  The `LLM Parser` creates a `Stimulus` with high "joy" and "excitement".
    2.  `Sentio Engine` processes this, and its internal state shifts to be more joyful.
    3.  When the user talks to the AI the next day, the `LLM Generator` receives a `Report` that still shows a slightly elevated level of joy.
    4.  The AI can then generate a response like, "It's great to talk to you again! Still feeling excited about the new job?"

#### Use Case 2: Dynamic NPCs in a Video Game

A game character's disposition towards the player can evolve based on in-game events.
- **Workflow:** The player completes a quest that helps a village.
- **Execution:**
    1.  The game's event system sends a `Stimulus` with "gratitude" and "trust" to the Sentio Engine instance tied to a specific NPC.
    2.  The NPC's internal state is updated.
    3.  The next time the player talks to the NPC, the dialogue system gets a `Report` indicating high trust.
    4.  The NPC's dialogue changes from generic greetings to warm and appreciative remarks, and they might even offer the player a discount at their shop.

## Installation

1.  **Install Poetry.** (See [official documentation](https://python-poetry.org/docs/#installation)).
2.  **Navigate to the project directory:** `cd sentio_engine`
3.  **Install dependencies:** `poetry install`
4.  **Install and Run MongoDB:** Ensure you have a running MongoDB instance locally or remote connection URI.

## Usage

### Running the Service
Run `poetry run uvicorn sentio_engine.api.main:app --reload` from within the `sentio_engine` directory.

### Running Tests
1.  Navigate to the `sentio_engine` directory.
2.  Run `poetry run pytest`.


## Roadmap

We are actively working to enhance the Sentio Engine. Key features on our roadmap include:

- [x] ~~**Redis Integration:** Offer an optional Redis backend for short-term memory.~~ (Implemented)
- [x] ~~**Agent Protocol:** Implemented an endpoint (`/process_agent_text`) for reliable state updates from LLM agents.~~ (Implemented)
- [x] ~~**Time Simulation:** Emotions now decay in real-time, even when the server is idle.~~ (Implemented)
- [x] ~~**Dominance Mechanism:** Opposing emotions (per Plutchik's model) now suppress each other.~~ (Implemented)
- [x] ~~**Complex States Engine:** The system can now identify long-term feelings (e.g., "depressive state") by analyzing history.~~ (Implemented)
- [x] ~~**Implement `BeliefSystem.json`:** Added a belief system based on the "Big Five" personality traits to modulate emotional responses.~~ (Implemented)
- [x] ~~**Multi-Tenancy:** Stateless architecture with MongoDB for handling multiple clients and sessions.~~ (Implemented)
- [x] ~~**Proxy Mode:** OpenAI-compatible proxy with "Subconscious" emotional injection.~~ (Implemented)
- [ ] **Implement `drives.json`:** Fully integrate the core drives system to influence emotional processing.
- [ ] **Admin Dashboard:** A simple web interface to visualize the engine's current emotional state in real-time.

## Full Documentation

For a deeper dive into the architecture, API, and configuration, please see the **[Full Documentation](./docs/en/01_introduction.md)**.
