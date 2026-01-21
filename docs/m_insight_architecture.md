# mInsight Intelligence Architecture

This document describes the end-to-end workflow for image intelligence processing in the mInsight system, covering face detection, face recognition, and multi-model embeddings (CLIP and DINOv2).

## Image Intelligence Workflow

The following diagram and table detail the interaction between the Store service, the Compute endpoint, and the persistence layers (SQLite and Qdrant).

### Sequence of Events

```mermaid
graph TD
    %% Workflow Start
    Start([Image Ingested]) --> Worker[mInsight Worker]
    
    %% Enqueue Phase
    subgraph SQLite ["SQLite DB"]
        ITL[(image_intelligence)]
        EJ[(entity_jobs)]
        F[(faces)]
        KP[(known_persons)]
        FM[(face_matches)]
    end

    Worker -->|1. Setup| ITL
    Worker -->|2. Trigger| Service[Intelligence Service]

    %% Compute Phase
    subgraph Compute ["Compute Service"]
        CE[Compute Endpoint]
        FDJ[Face Detection Job]
        CEJ[CLIP Embedding Job]
        DEJ[DINO Embedding Job]
        FEJ[Face Embedding Job]
    end

    Service -->|3. Submit| CE
    CE --> FDJ
    CE --> CEJ
    CE --> DEJ
    
    %% Logic & DB Updates
    FDJ -- Callback --> EJ
    FDJ -- Callback --> CB1[Handle Detect]
    CB1 -->|Write| F
    CB1 -->|Submit| CE
    CE --> FEJ

    CEJ -- Callback --> EJ
    CEJ -- Callback --> CB2[Handle CLIP]
    CB2 -->|Store| Q_CLIP[(Qdrant: CLIP)]

    DEJ -- Callback --> EJ
    DEJ -- Callback --> CB3[Handle DINO]
    CB3 -->|Store| Q_DINO[(Qdrant: DINO)]

    FEJ -- Callback --> EJ
    FEJ -- Callback --> CB4[Handle Face Embed]
    CB4 -->|Match & Link| KP
    CB4 -->|Record Match| FM
    CB4 -->|Store| Q_FACE[(Qdrant: FACE)]

    subgraph Qdrant ["Qdrant Vector Store"]
        Q_CLIP
        Q_DINO
        Q_FACE
    end
```

### Process & Data Flow

| Step              | Process                          | Action                             | Data Store Updated                                                  |
| :---------------- | :------------------------------- | :--------------------------------- | :------------------------------------------------------------------ |
| **1. Enqueue**    | `_enqueue_image`                 | Initialize status                  | `image_intelligence` (SQLite)                                       |
| **2. Trigger**    | `trigger_async_jobs`             | Submit 3 jobs (Detect, CLIP, DINO) | `entity_jobs` (SQLite)                                              |
| **3. Detection**  | `handle_face_detection_complete` | Save faces & Trigger embedding     | `faces` (SQLite), `entity_jobs` (SQLite)                            |
| **4. CLIP Embed** | `handle_clip_embedding_complete` | Save vector                        | `Qdrant: CLIP` collection                                           |
| **5. DINO Embed** | `handle_dino_embedding_complete` | Save vector                        | `Qdrant: DINO` collection                                           |
| **6. Face Embed** | `handle_face_embedding_complete` | Recognition & Save vector          | `known_persons`, `face_matches` (SQLite), `Qdrant: FACE` collection |
