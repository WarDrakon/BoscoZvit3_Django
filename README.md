# Roommate — система підтримки прийняття рішень для підбору співмешканців

Django 5.2 · MySQL 8 · Django Templates · JavaScript (Fetch API). Інтерфейс повністю українською.

## Можливості
- Реєстрація/вхід за email, відновлення пароля поштою, зміна пароля, деактивація та повне видалення акаунта.
- Профіль, анкета побутових звичок (факти) і параметри пошуку (вимоги) з «Неважливо», вагами 1–5 та критичними вимогами.
- Прозорий алгоритм сумісності (`matching/services.py`) без ML: нормалізована зважена оцінка, взаємність, критичні конфлікти, пояснення.
- Оголошення про житло з фото (перевірка формату/розміру), точна адреса прихована.
- Запити на контакт → приватний чат (Fetch API + опитування кожні 3 с), статуси прочитання, блокування, скарги.
- Django Admin: користувачі, скарги, приховування оголошень.

## Алгоритм у двох словах
Для пари A↔B у двох напрямках («вимоги A ↔ звички B» і навпаки) рахується оцінка sᵢ∈[0;1] за 10 критеріями.
Напрямкова оцінка `S = Σ(wᵢ·sᵢ) / Σwᵢ`. Критерії з «Неважливо» не враховуються. Якщо вимога є, а даних кандидата бракує, критерій отримує нейтральну оцінку 0,5 (невідомо ≠ збіг) і зменшує «повноту даних»; якщо порівняти нічого, оцінка не розраховується («Недостатньо даних»).
Взаємна сумісність `M = 0.6·середнє(S_AB, S_BA) + 0.4·min(S_AB, S_BA)` — мінімум штрафує односторонню відповідність.
Критичні вимоги (sᵢ < 0.5) та різні міста дають «критичний конфлікт»: такі кандидати не потрапляють в основні рекомендації.

## Налаштування MySQL
```sql
CREATE DATABASE roommate CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'roommate'@'localhost' IDENTIFIED BY 'ваш-пароль';
GRANT ALL PRIVILEGES ON roommate.* TO 'roommate'@'localhost';
FLUSH PRIVILEGES;
```
Для `mysqlclient` потрібні системні бібліотеки. Ubuntu/Debian: `sudo apt install python3-dev default-libmysqlclient-dev build-essential pkg-config`. macOS: `brew install mysql-client pkg-config`. Windows: зазвичай достатньо `pip install mysqlclient` (готове колесо).

## Запуск
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # відредагуйте значення
python manage.py migrate
python manage.py createsuperuser                       # email, ім’я, прізвище, пароль
python manage.py runserver
```
Відкрийте http://127.0.0.1:8000/ , адмінпанель — `/admin/`.

## Демонстраційні дані
Створіть **окрему** базу (наприклад, `roommate_demo`), вкажіть її в `DB_NAME`, виконайте `python manage.py migrate`, а потім:
```bash
mysqldump -u roommate -p roommate > backup_before_demo.sql   # резервна копія робочої бази (за потреби)
python manage.py seed_demo                  # 20 вигаданих профілів, 6 оголошень, запити й чат; повторний запуск не дублює записи
python manage.py seed_demo --purge-legacy   # додатково видалити старі тестові акаунти (@demo.ua, *.qa@example.test, *.run@example.test)
python manage.py seed_demo --reset          # видалити й створити заново лише демо-акаунти (@demo.roommate.local)
```
Вхід: `andriy.koval@demo.roommate.local` / `Demo-pass-123`. Усі профілі вигадані й позначені «(демонстраційний профіль)»; «фото» — ілюстрації, згенеровані кодом. Команда відмовляється працювати в базі без «demo» у назві (обхід — `--force`), не чіпає реальних користувачів і адміністраторів.

Якщо MySQL працює через сокет, у `.env` вкажіть `DB_HOST=localhost`; для TCP — `127.0.0.1`.

## Тести
```bash
python manage.py test                       # 136 тестів; потрібен доступ до MySQL (Django створить тестову БД)
DB_ENGINE=sqlite python manage.py test      # швидкий запуск без MySQL
```

## Підготовка до production
1. `DJANGO_DEBUG=False`, унікальний `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`.
2. Налаштуйте справжній SMTP (`EMAIL_*`) — інакше відновлення пароля не працюватиме.
3. `python manage.py collectstatic`; статику та `media/` віддає nginx (у `DEBUG=False` Django цього не робить).
4. Запускайте через gunicorn/uWSGI за nginx з HTTPS (`SECURE_SSL_REDIRECT` увімкнено автоматично).
5. Регулярні резервні копії MySQL і `media/`.
6. Перевірка: `python manage.py check --deploy`.

## Публікація на GitHub
```bash
git remote add origin https://github.com/<ваш-акаунт>/<репозиторій>.git   # якщо ще не додано
git push -u origin main                                                   # без --force
```
Перед push переконайтеся, що `git status` чистий, а `.env` і бази не потрапили в коміти (`git ls-files | grep -E "\.env$|sqlite"` має бути порожнім).

## Обмеження першої версії
- Тестова документація та результати перевірок постачаються окремо (`roommate_testing.zip`); автоматизовані тести Django лишаються в застосунках (`python manage.py test`).
- Верифікація особи не реалізована: перевіряється лише формат email, листа підтвердження реєстрації немає.
- Чат працює через опитування (затримка до 3 с); для масштабування можна перейти на Django Channels.
- Розрахунок рекомендацій виконується при кожному перегляді для всіх кандидатів — достатньо для сотень профілів; для тисяч потрібне кешування/попередня фільтрація в БД.
- Пошук по місту/району чутливий до регістру кирилиці залежно від колації БД (у MySQL utf8mb4_unicode_ci — нечутливий).
