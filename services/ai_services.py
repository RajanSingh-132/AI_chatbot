import os
import json
import re
from dotenv import load_dotenv
from google import genai

from mongo_client import mongo_client
from utils.request_tracker import tracker
from rag_retriever import RAGRetriever
from prompt import SYSTEM_PROMPT
from routes.upload import ACTIVE_DATASET

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY missing")

client = genai.Client(api_key=API_KEY)
tracker.gemini_hit()

retriever = RAGRetriever()


# ----------------------------
# ✅ FETCH DATA (MISSING FIX)
# ----------------------------
def fetch_data(dataset):

    if not dataset:
        return []

    db = mongo_client.db
    collection = db["documents"]

    result = collection.find_one({
        "type": "dataset",
        "file_name": dataset
    })

    return result.get("data", []) if result else []


# ----------------------------
# MAIN FUNCTION
# ----------------------------
def generate_ai_response(user_id: str, message: str, history=None) -> dict:

    query = message.lower().strip()
    dataset = ACTIVE_DATASET
    result = None

    print("ACTIVE DATASET:", dataset)

    # ----------------------------
    # CACHE CHECK
    # ----------------------------
    cached = None
    if dataset:
        cached = mongo_client.get_cached_result(dataset, query)

    if cached:
        print("⚡ FLOW: CACHE")

        result = {
            "answer": cached.get("answer", ""),
            "kpis": cached.get("kpis", []),
            "charts": cached.get("charts", [])
        }

    else:
        # ----------------------------
        # FETCH DATA
        # ----------------------------
        data = fetch_data(dataset)
        print("DATA LENGTH:", len(data))

        # ----------------------------
        # DATASET FLOW
        # ----------------------------
        if dataset and data:
            print("🧠 FLOW: DATASET AI")

            dataset_json = json.dumps(data[:50], indent=2)

            prompt = f"""
{SYSTEM_PROMPT}

Dataset:
{dataset_json}

User Query:
{message}

IMPORTANT:
Return ONLY JSON:
{{
  "answer": "string",
  "kpis": [],
  "charts": []
}}
"""

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )

                raw_text = response.text if hasattr(response, "text") else str(response)

                # 🔹 Clean
                raw_text = raw_text.replace("```json", "")
                raw_text = raw_text.replace("```", "")
                raw_text = raw_text.replace("\\n", " ")
                raw_text = raw_text.replace("\n", " ")
                raw_text = raw_text.replace("Answer:", "").strip()

                # 🔹 Extract JSON
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1

                if start != -1 and end != -1:
                    try:
                        parsed = json.loads(raw_text[start:end])

                        answer = parsed.get("answer", "").strip()
                        answer = re.sub(r"\s+", " ", answer)

                        result = {
                            "answer": answer,
                            "kpis": parsed.get("kpis", []),
                            "charts": parsed.get("charts", [])
                        }

                    except Exception as e:
                        print("❌ JSON Parse Error:", e)
                        result = {
                            "answer": "Error parsing AI response",
                            "kpis": [],
                            "charts": []
                        }
                else:
                    result = {
                        "answer": "Invalid AI response format",
                        "kpis": [],
                        "charts": []
                    }

            except Exception as e:
                print("❌ AI Error:", str(e))
                result = {
                    "answer": "AI service unavailable",
                    "kpis": [],
                    "charts": []
                }

        # ----------------------------
        # FALLBACK (RAG)
        # ----------------------------
        else:
            print("📚 FLOW: RAG FALLBACK")

            docs = retriever.get_relevant_documents(message)
            context = "\n\n".join(doc.page_content for doc in docs)

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"""
{SYSTEM_PROMPT}

Context:
{context}

User Query:
{message}

IMPORTANT:
Return ONLY JSON with this structure:
- answer: string
- kpis: array
- charts: array of objects with type and data
"""
                )

                raw_text = response.text if hasattr(response, "text") else str(response)

                # 🔹 Clean
                raw_text = raw_text.replace("```json", "")
                raw_text = raw_text.replace("```", "")
                raw_text = raw_text.replace("\\n", " ")
                raw_text = raw_text.replace("\n", " ")
                raw_text = raw_text.replace("Answer:", "").strip()

                # 🔹 Extract JSON
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1

                if start != -1 and end != -1:
                    try:
                        parsed = json.loads(raw_text[start:end])

                        answer = parsed.get("answer", "").strip()
                        answer = re.sub(r"\s+", " ", answer)

                        result = {
                            "answer": answer,
                            "kpis": parsed.get("kpis", []),
                            "charts": parsed.get("charts", [])
                        }

                    except:
                        result = {
                            "answer": raw_text.strip(),
                            "kpis": [],
                            "charts": []
                        }
                else:
                    result = {
                        "answer": raw_text.strip(),
                        "kpis": [],
                        "charts": []
                    }

            except Exception as e:
                print("❌ AI Error:", str(e))
                result = {
                    "answer": "AI service unavailable",
                    "kpis": [],
                    "charts": []
                }

    # ----------------------------
    # 🔥 SINGLE SAVE POINT
    # ----------------------------
    if result and result.get("answer"):
        print("🔥 SAVING FINAL RESULT:", query)

        mongo_client.save_result({
            "file_name": dataset or "rag_fallback",
            "query": query,
            "answer": result["answer"],
            "kpis": result["kpis"],
            "charts": result["charts"]
        })

    return result