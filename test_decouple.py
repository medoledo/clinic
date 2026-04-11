import sys
sys.path.append(r'C:\Users\medol\OneDrive\Desktop\clinic\clinic')
from decouple import config
print("GROQ is:", config('GROQ_API_KEY', default='NOT_FOUND'))
