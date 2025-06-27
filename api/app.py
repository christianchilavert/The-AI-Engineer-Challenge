# Import required FastAPI components for building the API
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
# Import Pydantic for data validation and settings management
from pydantic import BaseModel
# Import OpenAI client for interacting with OpenAI's API
from openai import OpenAI
import os
from typing import Optional

# Initialize FastAPI application with a title
app = FastAPI(title="OpenAI Chat API")

# Configure CORS (Cross-Origin Resource Sharing) middleware
# This allows the API to be accessed from different domains/origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin
    allow_credentials=True,  # Allows cookies to be included in requests
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers in requests
)

# Define the data model for chat requests using Pydantic
# This ensures incoming request data is properly validated
class ChatRequest(BaseModel):
    developer_message: str  # Message from the developer/system
    user_message: str      # Message from the user
    model: Optional[str] = "gpt-4.1"  # Optional model selection with default
    api_key: str          # OpenAI API key for authentication

# Lista de modelos a intentar, en orden de preferencia
MODEL_CANDIDATES = [
    "gpt-4.1-nano",
    "gpt-4.1-mini",
    "gpt-3.5-turbo",
    "gpt-4.1"
]

# Define the main chat endpoint that handles POST requests
@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        # Initialize OpenAI client with the provided API key
        client = OpenAI(api_key=request.api_key)
        
        # First, test all models to find one that works
        working_model = None
        last_exception = None
        
        for model_name in MODEL_CANDIDATES:
            try:
                # Test the model with a simple request
                test_response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": "test"}
                    ],
                    max_tokens=1
                )
                working_model = model_name
                print(f"Model {model_name} is working")
                break
            except Exception as e:
                last_exception = e
                print(f"Model {model_name} failed: {str(e)}")
                continue
        
        # If no model works, return error
        if not working_model:
            error_message = str(last_exception) if last_exception else "No models available"
            print(f"All models failed. Last error: {error_message}")
            
            # Check for specific error types and return appropriate status codes
            if "insufficient_quota" in error_message or "quota" in error_message.lower():
                raise HTTPException(status_code=429, detail=error_message)
            elif "model_not_found" in error_message:
                raise HTTPException(status_code=404, detail=error_message)
            elif "authentication" in error_message.lower() or "invalid_api_key" in error_message.lower():
                raise HTTPException(status_code=401, detail=error_message)
            else:
                raise HTTPException(status_code=500, detail=error_message)
        
        # Create an async generator function for streaming responses
        async def generate():
            stream = client.chat.completions.create(
                model=working_model,
                messages=[
                    {"role": "user", "content": request.user_message}
                ],
                stream=True  # Enable streaming response
            )
            
            # Yield each chunk of the response as it becomes available
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        # Return a streaming response to the client
        return StreamingResponse(generate(), media_type="text/plain")
    
    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        # Handle any other errors that occur during processing
        error_message = str(e)
        print(f"Error in /api/chat: {error_message}")
        raise HTTPException(status_code=500, detail=error_message)

# Define a health check endpoint to verify API status
@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# Entry point for running the application directly
if __name__ == "__main__":
    import uvicorn
    # Start the server on all network interfaces (0.0.0.0) on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
