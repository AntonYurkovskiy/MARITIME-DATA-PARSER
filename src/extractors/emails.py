
import re
from typing import Any


def find_emails(text) -> list[Any]:
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)


def get_emails_list(email_string):
    """Из строки с емейлами делает словарь по форме 
    {"email":"email", "comment":None, "uuid":"uuid"}

    Args:
        email_string (str): строка в которую должен входить email

    Returns:
        _type_: _description_
    """
    emails_list = []
    if find_emails(email_string):
        for email in find_emails(email_string):
            emails_list.append({"email": email, "comment": None, "uuid": None})
    else:
        return None
    # исправить чтобы не сохранял дублирующие емейлы, а сохранял только уникальные
    return emails_list
