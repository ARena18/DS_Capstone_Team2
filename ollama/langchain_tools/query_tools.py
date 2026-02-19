from langchain.tools import tool

from query import *
# Supported Queries/Functions
# - database_version
# - operation_period

# --- Declare tools ---
SUPPORTED_TOOL_MESSAGE = "I am not equipped with the knowledge to answer that question."  + \
                         "Instead, I can find you the following information: operation period, (functionality to be added...)."

@tool("operation_period")
def get_operation_period():
    """
    Gets the operation date for King County metro buses.
    
    Returns the start operation date and end operation date.
    """

    start, end = operation_period()
    result = "Operation period: " + start.strftime("%m-%d-%Y") + " to " + end.strftime("%m-%d-%Y")
    return result

TOOL_DICT = {
    "operation_period": get_operation_period,
}