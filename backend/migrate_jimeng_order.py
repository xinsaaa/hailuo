"""
数据库迁移脚本：为 JimengOrder 表添加新字段

在服务器上执行：
cd /home/ubuntu/hailuo && source venv/bin/activate && python migrate_jimeng_order.py
"""

import sqlite3

def migrate():
    conn = sqlite3.connect('hailuo.db')
    cursor = conn.cursor()
    
    # 检查并添加缺失的列
    migrations = [
        ('duration', 'INTEGER DEFAULT 5'),
        ('ratio', 'TEXT DEFAULT "16:9"'),
        ('resolution', 'TEXT DEFAULT "720P"'),
    ]
    
    for column_name, column_type in migrations:
        try:
            cursor.execute(f'SELECT {column_name} FROM jimengorder LIMIT 1')
            print(f'Column {column_name} already exists')
        except sqlite3.OperationalError:
            print(f'Adding column {column_name}...')
            cursor.execute(f'ALTER TABLE jimengorder ADD COLUMN {column_name} {column_type}')
            print(f'Column {column_name} added successfully')
    
    conn.commit()
    conn.close()
    print('Database migration completed!')

if __name__ == '__main__':
    migrate()
