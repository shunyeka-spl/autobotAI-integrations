# Import your modules here
import json
import traceback

# **Security Note:** Client-related modules should not be directly imported here.
# Instead, they are passed as arguments and retrieved from a secure configuration.


def executor(context):
    """
    Executes provided Python code within integrations.

    Args:
        context (dict): A dictionary containing information about the current execution.
            - params (dict): A dictionary containing parameters specified while creating action.
            - clients (dict): A dictionary that contain selected client objects while defining action. (The specific clients present and their usage depend on the specific action being executed.)

    Returns:
        list: Always returns an empty list (`[]`) or a list containing the results of the code execution. The specific content of the returned list depends on the code and how it interacts with the integration.
    """

    try:
        client = context["clients"]["python_http_requests"]
        # method: str, endpoint: str, headers: dict = dict()
        url = client.request("GET","",{"public" : "abc"})
        print(url.status_code)
    except Exception as e:
        print(traceback.format_exc())
    return {"success": True}
    # User's Python code execution logic goes here
    # (Replace this comment with the your actual code)

    # Example: Capitalizing the name of each dict from a list from parameters
    # res = []
    # for values in list(params["my_param"]):
    #     values["name"] = values["name"].capitalize()
    #     res.append(values)
    # return res
    # Replace with your actual return logic
