import os
import json
from pathlib import Path

def loadConfig(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception(f"Could not find config file: {file}")
    except json.JSONDecodeError:
        raise Exception(f"Could not parse config file: {file}")
    
def currPath():
    currPath = Path(__file__).resolve()
    root = next((p for p in currPath.parents if (p / '.git').exists()), None)

    if root is None:
        raise Exception("Could not find root directory")
    
    return str(currPath.parent.relative_to(root))
    