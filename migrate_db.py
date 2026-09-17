#!/usr/bin/env python3
"""Repair or rebuild the panel database for development.

`python migrate_db.py`          patch missing tables/columns in place
`python migrate_db.py --fresh`  drop everything and start over with a demo user
"""

import argparse
import os
import sqlite3

from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get('LODESTONE_DB', 'lodestone.db')

TABLES = {
    'users': {
        'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'username': 'TEXT UNIQUE NOT NULL',
        'password_hash': 'TEXT NOT NULL',
    },
    'servers': {
        'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'owner_id': 'INTEGER NOT NULL REFERENCES users(id)',
        'name': 'TEXT NOT NULL',
        'server_type': "TEXT NOT NULL DEFAULT 'PAPER'",
        'version': 'TEXT NOT NULL',
        'memory': "TEXT NOT NULL DEFAULT '2G'",
        'port': 'INTEGER NOT NULL UNIQUE',
        'rcon_password': 'TEXT NOT NULL',
        'created_at': 'TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP',
    },
}

DEMO_USER = ('admin', 'admin123')


def create(db, table):
    columns = ', '.join(f'{name} {definition}'
                        for name, definition in TABLES[table].items())
    db.execute(f'CREATE TABLE {table} ({columns})')


def addable(definition):
    # ALTER can't take NOT NULL/UNIQUE without a default, so keep those only
    # when the column already declares one
    if 'DEFAULT' not in definition:
        definition = definition.replace('NOT NULL', '').replace('UNIQUE', '').strip()
    return definition


def repair(db):
    changed = []
    for table, columns in TABLES.items():
        present = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
        if not present:
            create(db, table)
            changed.append(f'{table}: created')
            continue
        for name, definition in columns.items():
            if name not in present:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {addable(definition)}')
                changed.append(f'{table}.{name}: added')
    return changed


def fresh(db):
    for table in TABLES:
        db.execute(f'DROP TABLE IF EXISTS {table}')
    for table in TABLES:
        create(db, table)
    username, password = DEMO_USER
    db.execute(
        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
        (username, generate_password_hash(password)),
    )


def main():
    parser = argparse.ArgumentParser(description='Repair or reset the panel database.')
    parser.add_argument('--fresh', action='store_true',
                        help='drop all data and rebuild the schema with a demo user')
    args = parser.parse_args()

    with sqlite3.connect(DB_PATH) as db:
        if args.fresh:
            fresh(db)
            print(f'{DB_PATH}: rebuilt fresh')
            print(f'  demo login: {DEMO_USER[0]} / {DEMO_USER[1]}')
        else:
            changes = repair(db)
            if changes:
                for change in changes:
                    print(f'  {change}')
            else:
                print(f'{DB_PATH}: schema already up to date')

        ok = db.execute('PRAGMA integrity_check').fetchone()[0]
        print(f'integrity check: {ok}')
        if ok != 'ok':
            raise SystemExit(1)


if __name__ == '__main__':
    main()