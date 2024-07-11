# Import your modules here
import email, html
from datetime import datetime, timedelta

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

    params = context["params"]
    clients = context["clients"]

    # Placeholder for retrieving the integration-specific client if needed
    client = clients["imap_ssl_connection"]  # Supports only one client

    # User's Python code execution logic goes here
    # (Replace this comment with the your actual code)

    # Example: Code to list all yesterdays emails data (for illustration purposes only)
    client.select()

    yesterday_date = datetime.today() - timedelta(days=1)
    AFTER_DATE_FILTER = f'(SINCE "{yesterday_date.strftime("%d-%b-%Y")}")'
    emails_data = []
    result, data = client.search(None, AFTER_DATE_FILTER)
    if result == "OK":
        email_ids = data[0].split()

        # Get the most recent email
        if email_ids:
            for email_id in email_ids[::-1]:
                result, data = client.fetch(email_id, "(RFC822)")
                if result == "OK":
                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    email_data = {
                        "Subject": msg["Subject"],
                        "From": msg["From"],
                        "Body": "",
                    }
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            html_body = part.get_payload(decode=True).decode()
                            msg_body = (
                                html.unescape(html_body)
                                .replace("\r", "")
                                .replace("\n", " ")
                            )
                            email_data["Body"] += msg_body
                    emails_data.append(email_data)

            return email_data
    client.close()
    client.logout()
    return [{"result": "No emails found for yesterday"}]
