import csv
import re

def normalize_phone(raw: str) -> str | None:
    # оставляем только цифры
    digits = re.sub(r'\D', '', raw)

    if not digits:
        return None

    # если 11 цифр и начинается с 8 – меняем 8 на 7
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]

    # если 10 цифр (без кода страны) – добавляем 7
    if len(digits) == 10:
        digits = '7' + digits

    # финальная проверка: 11 цифр и начинается с 7
    if len(digits) == 11 and digits.startswith('7'):
        return digits

    # если номер «плохой» – можно вернуть None или исходник
    return None

input_file = r"C:\Users\Alex\Desktop\moysklad_phones_id.csv"
output_file = r"C:\Users\Alex\Desktop\moysklad_phones_id_normalized.csv"

with open(input_file, "r", encoding="cp1251", newline="") as f_in, \
     open(output_file, "w", encoding="utf-8", newline="") as f_out:
    reader = csv.reader(f_in, delimiter=';')
    writer = csv.writer(f_out, delimiter=';')

    # читаем заголовок
    header = next(reader)
    # создаём новый заголовок
    writer.writerow(["ID_normalized"])

    for row in reader:
        if not row:
            continue
        raw_phone = row[0]
        norm = normalize_phone(raw_phone)
        # можно пропускать плохие номера:
        if norm is None:
            continue
        writer.writerow([norm])

print("Готово:", output_file)