import os
import sys
import uvicorn

def print_banner():
    banner = """
======================================================================
   M A R K   2 . 0   --   A I   V I S U A L   A S S I S T A N T
   "Sees the world for you."

   * YOLOv8n Local Detection & Threat Engine
   * Gemini Vision Contextual Intelligence
   * Retell Voice Agent & Dynamic Speech Suppression
   * Supabase Cloud Telemetry & Session Logging

   HackSprint 2.0 -- AITAM
======================================================================
"""
    print(banner)
    print("-> Server starting at: http://localhost:5000")
    print("-> Open http://localhost:5000 in your browser to experience MARK 2.0\n")

if __name__ == "__main__":
    print_banner()
    uvicorn.run("server:app", host="0.0.0.0", port=5000, reload=False)
