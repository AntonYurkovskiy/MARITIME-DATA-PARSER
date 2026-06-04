from src.utils.validators import only_letters_digits_spaces


def get_personal_id_by_passport(pasports_list_of_dicts):
    priority_docs = ['International passport', 'National passport', "Seaman's book"]

    for doc_type in priority_docs:
        for doc in (pasports_list_of_dicts or []):
            if doc.get('Title of document') == doc_type:
                return doc['No.'] if only_letters_digits_spaces(doc['No.']) else None, doc_type

    return None, 'No documents'


def get_ranks(ranks):
    """Разбивает все ранги по '/' в плоский список"""
    all_ranks = [part.strip() for rank in ranks for part in rank.split('/')]
    return all_ranks