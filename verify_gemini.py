
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

print("--- Testing Gemini Configuration ---")

# 1. Load Environment
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ ERROR: GEMINI_API_KEY not found in environment variables.")
    sys.exit(1)
print(f"✅ Found GEMINI_API_KEY: {api_key[:5]}...{api_key[-5:]}")

# 2. Configure GenAI
try:
    genai.configure(api_key=api_key)
    print("✅ google-generativeai configured successfully.")
except Exception as e:
    print(f"❌ ERROR: Failed to configure genai: {e}")
    sys.exit(1)

# 3. List Models (to check connectivity)
try:
    print("Attempting to list models...")
    models = list(genai.list_models())
    print(f"✅ Successfully listed {len(models)} models.")
    gemini_models = [m.name for m in models if 'gemini' in m.name]
    print(f"   Available Gemini models: {gemini_models}")
except Exception as e:
    print(f"❌ ERROR: Failed to list models (Connectivity/Auth Issue): {e}")
    sys.exit(1)

# 4. Generate Content (Test Inference)
try:
    model_name = 'gemini-2.0-flash'
    print(f"Attempting inference with '{model_name}'...")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Hello")
    print(f"✅ Inference Successful! Response: {response.text.strip()}")
except Exception as e:
    print(f"❌ ERROR: Inference with {model_name} failed: {e}")
    
    try:
        model_name = 'gemini-flash-latest'
        print(f"Attempting inference with '{model_name}'...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hello")
        print(f"✅ Inference Successful with {model_name}! Response: {response.text.strip()}")
    except Exception as e:
       print(f"❌ ERROR: Inference with {model_name} failed: {e}")
       sys.exit(1)

print("--- Gemini Test Complete: SUCCESS ---")
