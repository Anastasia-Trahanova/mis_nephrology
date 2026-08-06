from __future__ import annotations
import argparse, getpass, os, subprocess, sys
from urllib.parse import quote
from pathlib import Path
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
DB=ROOT/'database'
CORE=[DB/'01 создание таблиц.sql',DB/'02 настройка связей ключей и ограничений.sql',DB/'03 заполнение справочников МКБ и лекарств.sql',DB/'04 справочник больницы и пользователи.sql']
CORE_CHECK=DB/'06 проверка структуры и справочников.sql'
DEMO=DB/'05 заполнение тестовыми данными.sql'
DEMO_CHECK=DB/'07 проверка тестовых данных.sql'
ARCHIVE_CHECK=DB/'08 проверка архивного расширения.sql'

def args():
 p=argparse.ArgumentParser()
 p.add_argument('--host',default=os.getenv('DB_HOST','localhost')); p.add_argument('--port',default=os.getenv('DB_PORT','5432'))
 p.add_argument('--user',default=os.getenv('DB_USER','postgres')); p.add_argument('--db-name',default=os.getenv('DB_NAME','mis_for_registrations'))
 p.add_argument('--admin-db',default='postgres'); p.add_argument('--password',default=os.getenv('DB_PASSWORD'))
 p.add_argument('--with-demo',action='store_true'); p.add_argument('--apply-archive',action='store_true')
 p.add_argument('--no-drop',action='store_true'); p.add_argument('--no-check',action='store_true'); p.add_argument('--yes',action='store_true')
 return p.parse_args()

def conn(a,name): return psycopg2.connect(host=a.host,port=a.port,user=a.user,password=a.password,dbname=name,client_encoding='UTF8')
def execute(a,path):
 if not path.exists(): raise FileNotFoundError(path)
 print('  ->',path.relative_to(ROOT)); c=conn(a,a.db_name)
 try:
  with c:
   with c.cursor() as cur: cur.execute(path.read_text(encoding='utf-8'))
 finally:c.close()

def recreate(a):
 if a.no_drop:return
 if not a.yes and input(f'База {a.db_name} будет удалена. Введите RESET: ').strip()!='RESET': raise SystemExit('Отменено')
 c=conn(a,a.admin_db); c.autocommit=True
 try:
  with c.cursor() as cur:
   cur.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()',(a.db_name,))
   cur.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(a.db_name)))
   cur.execute(sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(a.db_name)))
 finally:c.close()

def alembic(a):
 env=os.environ.copy(); env.update(DB_HOST=str(a.host),DB_PORT=str(a.port),DB_USER=str(a.user),DB_PASSWORD=str(a.password),DB_NAME=str(a.db_name),DATABASE_URL=f'postgresql://{quote(str(a.user), safe="")}:{quote(str(a.password), safe="")}@{a.host}:{a.port}/{quote(str(a.db_name), safe="")}',PYTHONUTF8='1')
 files=sorted(p for p in (ROOT/'migrations'/'versions').glob('*.py') if p.name!='__init__.py')
 if [p.name for p in files]!=['0018_archive_integration.py']: raise RuntimeError('В migrations/versions должен остаться только 0018_archive_integration.py')
 subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env,check=True)

def main():
 a=args(); a.password=a.password or getpass.getpass(f"Пароль PostgreSQL '{a.user}': ")
 if a.no_drop and not a.apply_archive: raise SystemExit('--no-drop используется вместе с --apply-archive')
 if a.no_drop:
  alembic(a)
  if not a.no_check: execute(a,ARCHIVE_CHECK)
 else:
  recreate(a)
  for p in CORE: execute(a,p)
  if not a.no_check: execute(a,CORE_CHECK)
  if a.with_demo:
   execute(a,DEMO)
   if not a.no_check: execute(a,DEMO_CHECK)
  if a.apply_archive:
   alembic(a)
   if not a.no_check: execute(a,ARCHIVE_CHECK)
 print('Готово:',a.db_name)

if __name__=='__main__': main()
