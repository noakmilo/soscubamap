# #SOSCuba Map

Dashboard colaborativo para documentar y visualizar lugares y acciones represivas en Cuba.

## Stack
- Python Flask
- PostgreSQL

## Configuración rápida
1. Crear entorno virtual e instalar dependencias
2. Copiar variables de entorno
3. Crear base de datos y ejecutar migraciones
4. Sembrar roles y categorías
5. Configurar admin por env
6. Ejecutar app

## Comandos sugeridos
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

createdb soscubamap

flask --app run.py db init
flask --app run.py db migrate -m "init"
flask --app run.py db upgrade

python -m scripts.seed_roles
python -m scripts.seed_categories

echo "ADMIN_EMAIL=admin@soscuba.local" >> .env
echo "ADMIN_PASSWORD=tu_password_seguro" >> .env

flask --app run.py run
```

## Roles
- colaborador: cuenta estandar
- moderador: revisa reportes
- administrador: gestiona usuarios y ajustes

## Nota
Los reportes se muestran como anónimos por defecto y pasan por moderación.
Si `ADMIN_EMAIL` y `ADMIN_PASSWORD` estan en `.env`, al hacer login se crea el usuario admin automaticamente.
