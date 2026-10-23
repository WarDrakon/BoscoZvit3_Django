"""Демонстраційні дані Roommate: 20 вигаданих українських профілів, оголошення, запити й чат.

Запуск (лише в окремій демонстраційній базі):
    python manage.py seed_demo                      # створити або оновити (безпечно повторювати)
    python manage.py seed_demo --purge-legacy       # додатково видалити старі тестові акаунти (див. LEGACY_SUFFIXES)
    python manage.py seed_demo --reset              # видалити та створити заново лише демо-акаунти
Усі демо-акаунти мають пошту @demo.roommate.local і пароль Demo-pass-123. Жодних справжніх людей:
імена вигадані, «фото» — ілюстрації, що генеруються кодом. Реальних користувачів команда не чіпає.
"""
import io
import random
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from PIL import Image, ImageDraw

from chat.models import Conversation, Message
from housing.models import HousingListing, HousingPhoto
from interactions.models import ContactRequest
from profiles.models import CRITERIA, CriterionWeight, LifestylePreference, SearchPreference

User = get_user_model()
DOMAIN = "demo.roommate.local"
PASSWORD = "Demo-pass-123"
# Лише такі «старі тестові» акаунти вважаються застарілими; реальних користувачів це не стосується.
LEGACY_SUFFIXES = ("@demo.ua", ".qa@example.test", ".run@example.test")
MARK = " (демонстраційний профіль)"

ANY = dict(req_sleep="any", req_min_cleanliness=None, req_max_noise=None, req_guests="any", req_smoking="any", req_pets="any", req_chores="any")


def H(sleep, clean, noise, guests, smoking, pets, work, chores):
    return dict(sleep_schedule=sleep, cleanliness=clean, noise_level=noise, guests_frequency=guests, smoking=smoking, pets=pets,
                work_schedule=work, chores_attitude=chores)


def S(city, district, lo, hi, days, **req):
    return dict(city=city, district=district, budget_min=lo, budget_max=hi, move_in_offset=days, **{**ANY, **req})


# ключ, ім’я, прізвище, режим, рід занять, про себе, звички, пошук, ваги, критичні, оголошення
PEOPLE = [
    ("andriy.koval", "Андрій", "Коваленко", "joint", "Студент, ІТ", "Рано встаю, люблю тишу й порядок. Шукаю спокійного співмешканця для спільної оренди.",
     H("early", 5, 2, "sometimes", "no", "none", "study", "split"),
     S("Львів", "Франківський", 5000, 8000, 21, req_sleep="early", req_min_cleanliness=4, req_max_noise=3, req_guests="sometimes", req_smoking="no_inside", req_chores="split"),
     {"budget": 5, "noise": 4, "cleanliness": 4, "smoking": 5}, {"smoking"}, None),
    ("olena.melnyk", "Олена", "Мельник", "has_housing", "Дизайнерка-фрилансерка", "Працюю вдома, тому цінуємо тишу. Здаю кімнату в трикімнатній квартирі.",
     H("early", 5, 2, "rare", "no", "none", "remote", "split"),
     S("Львів", "Сихівський", 6500, 8000, 14, req_min_cleanliness=4, req_max_noise=2, req_smoking="no_inside"),
     {"noise": 5, "cleanliness": 5}, set(),
     dict(title="Світла кімната біля парку", city="Львів", district="Сихівський", address="вул. Прикладна, 12 (вигадана адреса)", price=7200, rooms=3, free=1,
          description="Тиха трикімнатна квартира, ремонт 2024 року. У кімнаті ліжко, шафа, робочий стіл. Є пральна машина, швидкий інтернет, поруч парк і зупинка трамвая. Шукаю охайну людину без куріння в приміщенні.")),
    ("ihor.lytvyn", "Ігор", "Литвин", "has_housing", "Програміст", "Живу з котом Барсиком, працюю віддалено. Люблю, коли в домі спокійно, але без фанатизму.",
     H("late", 4, 3, "sometimes", "no", "has", "remote", "flexible"),
     S("Львів", "Галицький", 5000, 9000, 30),
     {"budget": 3}, set(),
     dict(title="Кімната в історичному центрі", city="Львів", district="Галицький", address="вул. Умовна, 7 (вигадана адреса)", price=8200, rooms=3, free=1,
          description="Простора кімната у старому будинку з високими стелями. Живу з котом. Вільний графік, спілкуюсь, але поважаю особистий простір. Комунальні платежі розділяємо порівну.")),
    ("mariia.shevchuk", "Марія", "Шевчук", "joint", "Аспірантка", "Багато читаю, вечорами працюю за ноутбуком. Курю лише на балконі.",
     H("regular", 4, 2, "rare", "outside", "none", "study", "split"),
     S("Львів", "Франківський", 5500, 7500, 28, req_min_cleanliness=3, req_max_noise=3),
     {"cleanliness": 4}, set(), None),
    ("taras.bondar", "Тарас", "Бондар", "joint", "Оператор кол-центру", "Працюю позмінно, тож режим нестандартний. Люблю гостей і гучну музику.",
     H("late", 3, 4, "often", "inside", "has", "shift", "flexible"),
     S("Львів", "Личаківський", 4000, 6500, 10), {}, set(), None),
    ("sofiia.honchar", "Софія", "Гончар", "joint", "Маркетологиня", "Працюю в офісі, вихідні проводжу активно. Дім для мене має бути чистим і без тютюнового диму.",
     H("regular", 5, 2, "sometimes", "no", "none", "office", "split"),
     S("Львів", "Франківський", 6000, 9000, 35, req_smoking="no_smokers", req_min_cleanliness=4),
     {"smoking": 5, "cleanliness": 5}, {"smoking"}, None),
    ("nazar.kravchuk", "Назар", "Кравчук", "has_housing", "Студент-медик", "Багато вчуся, потрібна тиша. Гостей приймаю рідко.",
     H("early", 4, 1, "never", "no", "none", "study", "split"),
     S("Львів", "Сихівський", 4500, 6000, 18, req_max_noise=2, req_guests="rare"),
     {"noise": 5}, set(),
     dict(title="Кімната у квартирі біля трамвая", city="Львів", district="Сихівський", address="вул. Тестова, 3 (вигадана адреса)", price=5200, rooms=2, free=1,
          description="Двокімнатна квартира, друга кімната вільна. Поруч магазини й зупинка. Прошу тишу після 22:00, бо багато вчусь.")),
    ("oleksii.hryniv", "Олексій", "Гринів", "joint", "Інженер-будівельник", "Звичайний розпорядок, без шкідливих звичок, люблю готувати.",
     H("regular", 3, 3, "sometimes", "outside", "none", "office", "flexible"),
     S("Львів", "Франківський", 5000, 8500, 40), {}, set(), None),
    ("viktoriia.kushnir", "Вікторія", "Кушнір", "joint", "Студентка", "Жайворонок, обожнюю порядок. Шукаю співмешканку або співмешканця для оренди поруч із центром.",
     H("early", 5, 2, "rare", "no", "none", "study", "split"),
     S("Львів", "Франківський", 5500, 8000, 52, req_sleep="early", req_min_cleanliness=4, req_max_noise=3, req_smoking="no_inside"),
     {"cleanliness": 5, "noise": 4}, set(), None),
    ("daryna.oliinyk", "Дарина", "Олійник", "joint", "UX-дизайнерка", "Працюю віддалено, іноді запрошую друзів на вечерю. Шукаю гнучкого співмешканця.",
     H("regular", 4, 3, "sometimes", "no", "none", "remote", "flexible"),
     S("Київ", "Печерський", 12000, 18000, 20, req_smoking="no_inside"), {}, set(), None),
    ("maksym.tkachenko", "Максим", "Ткаченко", "has_housing", "Інженер", "Маю собаку, багато гуляю. Шукаю товариську людину в трикімнатну квартиру.",
     H("late", 3, 4, "often", "outside", "has", "office", "flexible"),
     S("Київ", "Оболонський", 9000, 12000, 16), {}, set(),
     dict(title="Кімната біля набережної на Оболоні", city="Київ", district="Оболонський", address="просп. Вигаданий, 21 (вигадана адреса)", price=11000, rooms=3, free=2,
          description="Дві вільні кімнати у трикімнатній квартирі біля набережної. Є собака, тому квартира для тих, хто любить тварин. Меблі, інтернет, пральна машина включено.")),
    ("anastasiia.boiko", "Анастасія", "Бойко", "joint", "Юристка", "Цінюю чистоту й тишу, не терплю дим і тварин у квартирі.",
     H("early", 5, 2, "rare", "no", "none", "office", "split"),
     S("Київ", "Шевченківський", 13000, 19000, 25, req_min_cleanliness=4, req_max_noise=2, req_smoking="no_smokers", req_pets="no_pets"),
     {"smoking": 5, "pets": 5, "noise": 4}, {"smoking", "pets"}, None),
    ("vladyslav.moroz", "Владислав", "Мороз", "joint", "Студент", "Грає в гурті, тож у квартирі іноді гучно. Приятелів запрошую часто.",
     H("late", 2, 5, "often", "inside", "none", "study", "minimal"),
     S("Київ", "Деснянський", 7000, 10000, 12), {}, set(), None),
    ("kateryna.lysenko", "Катерина", "Лисенко", "has_housing", "Викладачка", "Живу з кішкою, працюю вдома, люблю спокійні вечори.",
     H("regular", 4, 2, "rare", "no", "has", "remote", "split"),
     S("Харків", "Київський", 5500, 7500, 30, req_smoking="no_inside"), {"smoking": 4}, set(),
     dict(title="Затишна кімната у Київському районі", city="Харків", district="Київський", address="вул. Умовна, 15 (вигадана адреса)", price=6000, rooms=2, free=1,
          description="Світла кімната у двокімнатній квартирі. Живу з кішкою. Поруч метро й супермаркет. Шукаю спокійну людину без куріння в приміщенні.")),
    ("bohdan.pavlenko", "Богдан", "Павленко", "joint", "Програміст", "Працюю віддалено, ввечері люблю ігри та кіно. Курю на вулиці.",
     H("late", 3, 3, "sometimes", "outside", "none", "remote", "flexible"),
     S("Харків", "Салтівський", 5000, 8000, 22), {}, set(), None),
    ("yuliia.romaniuk", "Юлія", "Романюк", "joint", "Адміністраторка готелю", "Працюю змінами, тому режим непередбачуваний. Спокійна й дружня.",
     H("late", 3, 3, "sometimes", "no", "none", "shift", "flexible"),
     S("Одеса", "Приморський", 8000, 12000, 15, req_smoking="no_inside"), {}, set(), None),
    ("artem.savchenko", "Артем", "Савченко", "has_housing", "Портовий інженер", "Часто на змінах, удома тиша й порядок. Здаю кімнату в квартирі біля моря.",
     H("regular", 4, 2, "rare", "no", "none", "shift", "split"),
     S("Одеса", "Київський", 7000, 10000, 26, req_min_cleanliness=3), {}, set(),
     dict(title="Кімната неподалік від моря", city="Одеса", district="Київський", address="вул. Приклад, 9 (вигадана адреса)", price=9000, rooms=2, free=1,
          description="Світла кімната з балконом у двокімнатній квартирі. До моря 15 хвилин пішки. Графік змінний, тому в квартирі зазвичай тихо.")),
    ("oksana.hnatiuk", "Оксана", "Гнатюк", "joint", "Бухгалтерка", "Тиха, охайна, не приймаю гостей. Шукаю спокійне житло в центрі.",
     H("early", 5, 1, "never", "no", "none", "office", "split"),
     S("Дніпро", "Центральний", 6000, 9000, 19, req_max_noise=2, req_guests="rare", req_smoking="no_inside"), {"noise": 5}, set(), None),
    ("roman.stelmakh", "Роман", "Стельмах", "joint", "ІТ-спеціаліст", "Маю собаку середнього розміру. Працюю віддалено й багато гуляю.",
     H("regular", 4, 3, "sometimes", "no", "has", "remote", "flexible"),
     S("Івано-Франківськ", "Центр", 5000, 8000, 33), {}, set(), None),
    ("iryna.danyliuk", "Ірина", "Данилюк", "joint", "Вчителька", "Спокійна, люблю садівництво й читання. Шукаю співмешканку.",
     H("regular", 4, 2, "rare", "no", "none", "office", "split"),
     S("Тернопіль", "Центр", 4500, 6500, 27, req_smoking="no_inside"), {}, set(), None),
]

# (від кого, кому, статус, [(автор, текст, хвилин тому, прочитано)])
CHATS = [
    ("andriy.koval", "olena.melnyk", "accepted", True, [
        ("andriy.koval", "Доброго дня, Олено! Побачив ваше оголошення на Сихові. Кімната ще вільна?", 2900, True),
        ("olena.melnyk", "Вітаю, Андрію! Так, вільна. Є пральна машина й швидкий інтернет.", 2860, True),
        ("andriy.koval", "Чудово. Я рано встаю й не палю, а тиша для мене дуже важлива.", 2840, True),
        ("olena.melnyk", "Це якраз підходить: у нас тихо після 22:00, гості бувають рідко.", 2800, True),
        ("andriy.koval", "Можна переглянути кімнату в суботу?", 95, False)]),
    ("viktoriia.kushnir", "andriy.koval", "accepted", False, [
        ("viktoriia.kushnir", "Привіт! Побачила, що ми схожі за режимом і бюджетом. Ви ще шукаєте квартиру?", 600, True),
        ("andriy.koval", "Привіт, Вікторіє! Так, дивлюсь варіанти біля центру до 8000 на людину.", 540, True),
        ("viktoriia.kushnir", "Чудово, у мене схожий бюджет. Можемо разом подивитися пару квартир.", 20, False)]),
    ("ihor.lytvyn", "mariia.shevchuk", "accepted", False, [
        ("mariia.shevchuk", "Добрий день, Ігоре! Цікавить кімната в центрі. Кіт — це не проблема.", 1500, True),
        ("ihor.lytvyn", "Привіт, Маріє! Дякую. Коли вам зручно приїхати подивитись?", 1440, True)]),
    ("oleksii.hryniv", "andriy.koval", "pending", False, []),
    ("sofiia.honchar", "andriy.koval", "pending", False, []),
    ("taras.bondar", "andriy.koval", "declined", False, []),
]

W, Hh = 900, 560
GRADS = [("#5B3BF0", "#FF7A59"), ("#1B1650", "#7C5CFF"), ("#C23A24", "#FFB84D"), ("#12704C", "#5BD6B0"), ("#2B2377", "#FF8A70"), ("#4527CC", "#8FD3FF")]
WALLS = ["#EFE7DD", "#E4E9F3", "#F3E6E1", "#E6EFE8", "#EDE6F4"]


def _mix(a, b, t):
    a, b = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (a, b)]
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_avatar(index):
    """Абстрактний силует на градієнті (не фото людини)."""
    rng = random.Random(index)
    c1, c2 = GRADS[index % len(GRADS)]
    img = Image.new("RGB", (360, 360))
    d = ImageDraw.Draw(img)
    for y in range(360):
        d.line([(0, y), (360, y)], fill=_mix(c1, c2, y / 359))
    for _ in range(4):
        r = rng.randint(40, 110); x, y = rng.randint(0, 360), rng.randint(0, 360)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255), width=2)
    d.ellipse([105, 235, 255, 420], fill=(255, 255, 255))
    d.ellipse([130, 70, 230, 190], fill=(255, 255, 255))
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


def make_room(seed, variant):
    """Проста ілюстрація інтер’єру (не фото)."""
    rng = random.Random(seed * 31 + variant)
    wall = WALLS[(seed + variant) % len(WALLS)]
    img = Image.new("RGB", (W, Hh), wall)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 380, W, Hh], fill=_mix("#B88A5B", "#8A6038", rng.random()))
    wx = rng.choice([90, 560]); d.rectangle([wx, 80, wx + 250, 300], fill="#FFFFFF"); d.rectangle([wx + 10, 90, wx + 240, 290], fill=_mix("#8FD3FF", "#FFE9B8", rng.random()))
    d.line([(wx + 125, 90), (wx + 125, 290)], fill="#FFFFFF", width=6)
    if variant % 3 == 0:  # ліжко
        d.rounded_rectangle([300, 300, 720, 440], 18, fill="#5B3BF0"); d.rounded_rectangle([300, 270, 720, 330], 18, fill="#EEEAFF"); d.rounded_rectangle([330, 300, 420, 340], 10, fill="#FFFFFF")
    elif variant % 3 == 1:  # диван
        d.rounded_rectangle([260, 300, 700, 430], 24, fill="#C23A24"); d.rounded_rectangle([260, 260, 700, 330], 24, fill="#E2563B"); d.ellipse([320, 320, 380, 370], fill="#FFB84D")
    else:  # стіл і крісло
        d.rectangle([280, 330, 660, 350], fill="#38334F"); d.rectangle([300, 350, 316, 470], fill="#38334F"); d.rectangle([624, 350, 640, 470], fill="#38334F"); d.rounded_rectangle([420, 250, 560, 330], 6, fill="#17132E")
    d.ellipse([40, 300, 130, 380], fill="#12704C"); d.rectangle([76, 370, 94, 430], fill="#8A6038")
    d.polygon([(820, 420), (800, 300), (860, 300)], fill="#FFB84D"); d.rectangle([826, 420, 834, 470], fill="#38334F")
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=84); return buf.getvalue()


class Command(BaseCommand):
    help = "Створює (або оновлює) демонстраційні профілі, оголошення, запити й чат. Безпечно запускати повторно."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Спочатку видалити демо-акаунти (лише @%s)" % DOMAIN)
        parser.add_argument("--purge-legacy", action="store_true", help="Видалити старі тестові акаунти за списком суфіксів LEGACY_SUFFIXES")
        parser.add_argument("--force", action="store_true", help="Дозволити запуск у базі, назва якої не містить «demo»")

    def handle(self, *args, **opts):
        db = str(settings.DATABASES["default"]["NAME"])
        if "demo" not in db.lower() and not opts["force"]:
            raise CommandError(f"Базу «{db}» не визнано демонстраційною (у назві немає «demo»). Використайте окрему базу або --force.")
        if opts["purge_legacy"]:
            n = self._purge(lambda e: e.endswith(LEGACY_SUFFIXES))
            self.stdout.write(f"Видалено старих тестових акаунтів: {n}")
        if opts["reset"]:
            n = self._purge(lambda e: e.endswith("@" + DOMAIN))
            self.stdout.write(f"Видалено демо-акаунтів перед створенням: {n}")
        users = {}
        for i, row in enumerate(PEOPLE):
            users[row[0]] = self._person(i, row)
        for sender, receiver, status, with_listing, msgs in CHATS:
            self._chat(users, sender, receiver, status, with_listing, msgs)
        self.stdout.write(self.style.SUCCESS(
            f"Готово: профілів {len(PEOPLE)}, оголошень {HousingListing.objects.filter(owner__email__endswith='@' + DOMAIN).count()}. "
            f"Вхід: andriy.koval@{DOMAIN} / {PASSWORD}"))

    def _purge(self, match):
        doomed = [u for u in User.objects.all() if match(u.email.lower()) and not u.is_staff and not u.is_superuser]
        for user in doomed:
            user.delete()
        return len(doomed)

    def _person(self, i, row):
        key, first, last, mode, job, about, habits, search, weights, critical, listing = row
        email = f"{key}@{DOMAIN}"
        user, created = User.objects.get_or_create(email=email, defaults={"first_name": first, "last_name": last})
        if created:
            user.set_password(PASSWORD)
            user.save()
        p = user.profile
        p.display_name, p.city, p.occupation, p.search_mode, p.is_active_search = first, search["city"], job, mode, True
        p.about = about + MARK
        p.move_in_date = date.today() + timedelta(days=search["move_in_offset"])
        if not p.photo:
            p.photo.save(f"demo_{key}.png", ContentFile(make_avatar(i)), save=False)
        p.save()
        LifestylePreference.objects.update_or_create(profile=p, defaults=habits)
        s = {k: v for k, v in search.items() if k != "move_in_offset"}
        s["move_in_date"] = p.move_in_date
        SearchPreference.objects.update_or_create(profile=p, defaults=s)
        for crit, _ in CRITERIA:
            CriterionWeight.objects.update_or_create(profile=p, criterion=crit, defaults={"weight": weights.get(crit, 3), "is_critical": crit in critical})
        if listing:
            self._listing(i, user, listing)
        return user

    def _listing(self, i, user, data):
        fields = dict(city=data["city"], district=data["district"], address=data["address"], price_per_person=data["price"], rooms=data["rooms"],
                      free_places=data["free"], description=data["description"], is_active=True, is_hidden=False)
        listing, _ = HousingListing.objects.update_or_create(owner=user, title=data["title"], defaults=fields)
        if listing.photos.count() != 3:
            for ph in listing.photos.all():
                ph.image.delete(save=False)
                ph.delete()
            for v in range(3):
                photo = HousingPhoto(listing=listing)
                photo.image.save(f"demo_room_{user.pk}_{v}.jpg", ContentFile(make_room(i, v)), save=True)

    def _chat(self, users, sender, receiver, status, with_listing, msgs):
        a, b = users[sender], users[receiver]
        listing = HousingListing.objects.filter(owner=b).first() if with_listing else None
        req = ContactRequest.objects.filter(sender=a, receiver=b).first() or ContactRequest(sender=a, receiver=b)
        req.status, req.housing = status, listing
        req.message = {"pending": "Доброго дня! Ми добре підходимо за анкетою, буду рада(ий) познайомитись.", "declined": "Привіт! Шукаю співмешканця."}.get(status, "Доброго дня! Мене зацікавила ваша анкета.")
        if status != "pending":
            req.responded_at = timezone.now()
        req.save()
        if status != "accepted" or not msgs:
            return
        conv = Conversation.objects.get_or_create_between(a, b)
        if conv.messages.exists():
            return  # повторний запуск не дублює повідомлення
        for author, text, minutes_ago, read in msgs:
            m = Message.objects.create(conversation=conv, sender=users[author], text=text)
            when = timezone.now() - timedelta(minutes=minutes_ago)
            Message.objects.filter(pk=m.pk).update(created_at=when, read_at=when + timedelta(minutes=3) if read else None)
        Conversation.objects.filter(pk=conv.pk).update(updated_at=timezone.now() - timedelta(minutes=msgs[-1][2]))
