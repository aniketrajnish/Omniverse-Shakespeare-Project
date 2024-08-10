# Shakespeare AI : Vision + Realtime conversation + Facial Animation

A immersive experience allowing for real-time conversation with the digital twin of William Shakespeare. The conversations are context-aware as well as visually engaging with facial animations. It has vision capabilities as well, giving the user the ability to show images to Shakespeare and talk about them. The model has been fine-tuned by training on over 5M+ characters of Shakespeare's works.

The project leverages:

- Gemini API for image analysis and context generation. We're using the gemini-1.5-turbo model.
- Convai API for real-time conversation. We're using voices from ElevenLabs to generate natural-sounding speech.
- NVIDIA Omniverse's Audio2Face for facial animation as well as DLSS for frame generation to optimize performance.

## How it works
```mermaid
graph TD
    A[User opens project from Omniverse extension] --> B[Project loads in Audio2Face]
    B --> C[User clicks 'Connect to Server']
    C --> D[Socket server starts] & E[PyQt5 executable opens]
    E --> F[Executable connects to socket server]
    F --> G[PyQt5 window ready for interaction]
    G --> H{User selects image?}
    H -->|Yes| I[Image sent to Gemini API]
    I --> J[Update Shakespeare context in Convai API]
    H -->|No| K[User initiates conversation]
    J --> K
    K --> KA[Mic input captured using PyAudio]
    KA --> KB[Audio sent to Convai server]
    KB --> L[Convai generates audio response via gRPC]
    L --> M[Audio processed with pydub]
    M --> N[Processed audio sent to A2F socket server]
    N --> O[Audio added to queue using threading.Condition]
    O --> P[pydub removes clicks between chunks]
    P --> Q[Audio sent in chunks to A2F streaming audio player]
    Q --> R[A2F streaming audio player processes audio]
    R --> S[Audio converted to blendshapes for facial animation]
    S --> T[Auto emotions enabled based on audio]
    T --> U[DLSS used for frame generation]
    U --> V[Animated Shakespeare character displayed]
    V --> W[Conversation continues]
    W --> K
    W --> X[User ends conversation]
    X --> Y[Cleanup and disconnect]

    subgraph Omniverse[Omniverse Extension]
        A
        B
        C
        D
    end

    subgraph Bridge[Version Bridge]
        D[Socket server starts]
        F[PyQt5 executable<br>connects via sockets]
    end

    subgraph PyQt[PyQt5 Application]
        E[PyQt5 v5.15.2]
        G
        H
    end

    subgraph API[API Interactions]
        I[requests library<br>for Gemini API]
        J[requests library<br>for Convai API]
    end

    subgraph Convai[Convai Integration]
        K
        KA[Mic input captured<br>using PyAudio]
        KB[Data to<br>Convai server]
        L[gRPC v1.65.1<br>protobuf v4.21.10]
    end

    subgraph Audio[Audio Processing]
        M[pydub library]
        N[struct for packing<br>audio data]
        O[threading<br>queue.deque]
    end

    subgraph A2F[Audio2Face Integration]
        P[pydub removes clicks<br>between chunks]
        Q[A2F streaming audio player]
        R
        S
        T
        U
    end

    %% Adjust layout for 16:9
    Omniverse --> PyQt
    Bridge --> API
    Convai --> Audio
    Audio --> A2F
```
- **Project Initialization:**
    - The user opens the project from the Omniverse extension.
    - The project loads in Audio2Face.
- **Server Connection:**
    - The user connects to the socket server from the extension.
    - This action starts a socket server and opens a compiled PyQt5 executable.
- **User Interaction:**
    - Users can choose to select an image or start talking directly.
    - If an image is selected, it's sent to the `Gemini` API for analysis.
    - The context generated is updated in the `Convai` API to update the conversation context.
- **Conversation Flow:**
    - Microphone input is captured using `PyAudio`.
    - User speech is sent to the `Convai` service via `gRPC`.
    - The response is generated in shakespearean style and sent back.
- **Audio Processing:**
    - The audio response is processed using the `pydub` library.
    - Processed audio is sent to the Audio2Face socket server in chunks.
    - The audio is added to a queue using `threading.Condition`.
    - Clicks between audio chunks are also removed using `pydub`.
- **Facial Animation & Display:**
    - Audio is sent in chunks to the `Audio2Face` streaming audio player
    - The audio is processed and converted to blendshapes for facial animation.
    - Auto emotions are enabled based on the audio.
    - `DLSS` is used for frame generation to optimize performance.
    - The animated Shakespeare character is displayed, speaking the generated response.
- **Conversation Loop:**
    - The conversation continues until the user ends it.
    - At the end, the system cleans up and disconnects.