# Import your modules here
# **Security Note:** Client-related modules should not be directly imported here.
# Instead, they are passed as arguments and retrieved from a secure configuration.


def executor(context):
    """
    Executes provided Python code within integrations.

    Args:
        context (dict): A dictionary containing information about the current execution.
            - params (dict): A dictionary containing parameters specified while creating action.
            - clients (dict): A dictionary that contain selected client objects while defining action.

    Returns:
        list: A list of result rows.
    """

    params = context["params"]
    clients = context["clients"]
    client = clients["cymulate"]

    # Example: list environments with the official Cymulate OAuth2 client
    # environments = client.get("/v1/environments")
    # if isinstance(environments, list):
    #     return environments
    # if isinstance(environments, dict):
    #     return environments.get("data") or [environments]
    # return []

    return []
