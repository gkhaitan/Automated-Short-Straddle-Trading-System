import streamlit.cli
import os
import sys

def main():
    """
    Main function to run the trading bot.
    It launches the Streamlit UI.
    """
    # Add the project root to the Python path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

    ui_file = os.path.join(os.path.dirname(__file__), 'ui', 'app.py')

    # Using streamlit.cli.run directly
    # The first argument is the script path, the second is the list of arguments
    streamlit.cli.run([ui_file])

if __name__ == "__main__":
    main()
