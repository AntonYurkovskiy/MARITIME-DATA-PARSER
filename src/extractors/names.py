from src.utils.validators import only_letters_regex


def get_names(names_string):
    # предполагаем что первым идет имя
    name = only_letters_regex(names_string.split(' ')[0])
    name = name if name else 'Field is Empty / Поле не заполненно'
    # все что в середине здесь
    middle_name = only_letters_regex(names_string.split(' ',1)[1].rsplit(' ',1)[0] if len(names_string.split(' ')) > 2 else None)
    # фамилия в конце
    surname = only_letters_regex(names_string.split(' ')[-1])
    surname = surname if surname else 'Field is Empty / Поле не заполненно'
    return name, middle_name, surname