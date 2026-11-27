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

    clients = context["clients"]
    rf_client = clients["recorded_future"]

    try:
        response = rf_client.request(
            "get",
            "https://api.recordedfuture.com/v2/ip/8.8.8.8",
            params={"fields": "entity"},
        )
    except Exception as e:
        return [{"status": "error", "message": str(e)}]

    return [{"status": "success", "data": response.json()}]