import os

def cls():
    os.system('cls' if os.name == 'nt' else 'clear')
    
class console_colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    
def colorize(*text:str, color: str):
    return color+ ' '.join(text) + console_colors.ENDC
