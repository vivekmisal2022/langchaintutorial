"""
Alternative server runner using uvicorn programmatically.
This bypasses the uvicorn.exe executable that may be blocked by antivirus.
"""
import sys
import os

# Add backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    import uvicorn
    
    # Run uvicorn programmatically instead of as executable
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[backend_dir],
        log_level="info"
    )
