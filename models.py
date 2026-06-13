"""
六级词汇背诵App - 数据模型与记忆算法
Python课程作业版本 - 使用SQLite + 艾宾浩斯遗忘曲线
"""
import sqlite3
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "recite_words.db"
DATA_PATH = Path(__file__).parent / "data" / "cet6_words.json"


def get_db():
    """获取数据库连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_db()
    cursor = conn.cursor()

    # 单词表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL UNIQUE,
            phonetic_uk TEXT,
            phonetic_us TEXT,
            meanings TEXT,  -- JSON格式
            exam_meaning TEXT,
            frequency TEXT,  -- JSON格式
            example TEXT,  -- JSON格式
            etymology TEXT,
            derivatives TEXT,  -- JSON格式
            book TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 用户学习记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            status TEXT DEFAULT 'new',  -- new/learning/review/mastered
            familiarity INTEGER DEFAULT 0,  -- 熟悉度 0-100
            correct_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0,
            last_review_at TIMESTAMP,
            next_review_at TIMESTAMP,
            review_interval INTEGER DEFAULT 1,  -- 复习间隔（天）
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES words(id)
        )
    ''')

    # 学习日志表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            action TEXT,  -- learn/review/spell/listen
            result TEXT,  -- correct/wrong/ambiguous
            response_time INTEGER,  -- 响应时间（毫秒）
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES words(id)
        )
    ''')

    # 每日统计表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            new_learned INTEGER DEFAULT 0,
            reviewed INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0,
            study_minutes INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()


def load_words_from_json():
    """从JSON加载词库到数据库"""
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = get_db()
    cursor = conn.cursor()

    for word_data in data.get('words', []):
        cursor.execute('''
            INSERT OR IGNORE INTO words
            (id, word, phonetic_uk, phonetic_us, meanings, exam_meaning,
             frequency, example, etymology, derivatives, book)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            word_data['id'],
            word_data['word'],
            word_data.get('phonetic_uk', ''),
            word_data.get('phonetic_us', ''),
            json.dumps(word_data.get('meanings', []), ensure_ascii=False),
            word_data.get('exam_meaning', ''),
            json.dumps(word_data.get('frequency', {}), ensure_ascii=False),
            json.dumps(word_data.get('example', {}), ensure_ascii=False),
            word_data.get('etymology', ''),
            json.dumps(word_data.get('derivatives', []), ensure_ascii=False),
            word_data.get('book', 'cet6_core')
        ))

    conn.commit()
    conn.close()

    # 初始化学习记录
    init_learning_records()


def init_learning_records():
    """为所有新单词创建学习记录"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO learning_records (word_id, status, next_review_at)
        SELECT id, 'new', datetime('now') FROM words
        WHERE id NOT IN (SELECT word_id FROM learning_records)
    ''')

    conn.commit()
    conn.close()


# ============== 艾宾浩斯记忆算法 ==============

Ebbinghaus_INTERVALS = [1, 2, 4, 7, 15, 30, 90]  # 标准艾宾浩斯复习间隔


def calculate_next_review(familiarity, correct_count, wrong_count, current_interval):
    """
    基于艾宾浩斯遗忘曲线的智能复习间隔计算

    参数:
        familiarity: 熟悉度 (0-100)
        correct_count: 连续正确次数
        wrong_count: 错误次数
        current_interval: 当前间隔天数

    返回:
        next_interval: 下次复习间隔（天）
    """
    # 基础间隔根据正确次数选择
    if correct_count < len(Ebbinghaus_INTERVALS):
        base_interval = Ebbinghaus_INTERVALS[correct_count]
    else:
        base_interval = Ebbinghaus_INTERVALS[-1]

    # 根据熟悉度调整
    if familiarity >= 80:
        multiplier = 1.5
    elif familiarity >= 60:
        multiplier = 1.0
    elif familiarity >= 40:
        multiplier = 0.7
    else:
        multiplier = 0.5

    # 根据错误率惩罚
    total = correct_count + wrong_count
    if total > 0:
        accuracy = correct_count / total
        if accuracy < 0.5:
            multiplier *= 0.6
        elif accuracy < 0.7:
            multiplier *= 0.8

    next_interval = max(1, int(base_interval * multiplier))

    # 如果错误多，缩短间隔
    if wrong_count > correct_count:
        next_interval = max(1, next_interval // 2)

    return next_interval


def update_word_progress(word_id, result, response_time=None):
    """
    更新单词学习进度

    参数:
        result: 'correct', 'wrong', 'ambiguous'
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM learning_records WHERE word_id = ?
    ''', (word_id,))
    record = cursor.fetchone()

    if not record:
        conn.close()
        return

    record = dict(record)
    familiarity = record['familiarity'] or 0
    correct_count = record['correct_count'] or 0
    wrong_count = record['wrong_count'] or 0
    current_interval = record['review_interval'] or 1

    # 更新熟悉度和计数
    if result == 'correct':
        familiarity = min(100, familiarity + 15)
        correct_count += 1
    elif result == 'wrong':
        familiarity = max(0, familiarity - 20)
        wrong_count += 1
        correct_count = max(0, correct_count - 1)  # 错误时减少正确次数
    elif result == 'ambiguous':
        familiarity = min(100, familiarity + 5)

    # 计算下次复习时间
    next_interval = calculate_next_review(familiarity, correct_count, wrong_count, current_interval)
    next_review = datetime.now() + timedelta(days=next_interval)

    # 更新状态
    if familiarity >= 90 and correct_count >= 5:
        status = 'mastered'
    elif familiarity >= 40 or correct_count >= 1:
        status = 'review'
    else:
        status = 'learning'

    cursor.execute('''
        UPDATE learning_records
        SET status = ?, familiarity = ?, correct_count = ?, wrong_count = ?,
            last_review_at = datetime('now'), next_review_at = ?,
            review_interval = ?
        WHERE word_id = ?
    ''', (status, familiarity, correct_count, wrong_count,
          next_review.strftime('%Y-%m-%d %H:%M:%S'), next_interval, word_id))

    # 记录学习日志
    cursor.execute('''
        INSERT INTO study_logs (word_id, action, result, response_time)
        VALUES (?, 'review', ?, ?)
    ''', (word_id, result, response_time))

    conn.commit()
    conn.close()

    # 更新每日统计
    update_daily_stats(result)


def update_daily_stats(result):
    """更新每日学习统计"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM daily_stats WHERE date = ?', (today,))
    stats = cursor.fetchone()

    if stats:
        stats = dict(stats)
        if result == 'correct':
            cursor.execute('''
                UPDATE daily_stats
                SET reviewed = reviewed + 1, correct_count = correct_count + 1
                WHERE date = ?
            ''', (today,))
        elif result == 'wrong':
            cursor.execute('''
                UPDATE daily_stats
                SET reviewed = reviewed + 1, wrong_count = wrong_count + 1
                WHERE date = ?
            ''', (today,))
        else:
            cursor.execute('''
                UPDATE daily_stats SET reviewed = reviewed + 1 WHERE date = ?
            ''', (today,))
    else:
        # 新一天，计算连续打卡
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        cursor.execute('SELECT streak FROM daily_stats WHERE date = ?', (yesterday,))
        yesterday_stats = cursor.fetchone()
        streak = (yesterday_stats['streak'] + 1) if yesterday_stats else 1

        correct = 1 if result == 'correct' else 0
        wrong = 1 if result == 'wrong' else 0

        cursor.execute('''
            INSERT INTO daily_stats (date, reviewed, correct_count, wrong_count, streak)
            VALUES (?, 1, ?, ?, ?)
        ''', (today, correct, wrong, streak))

    conn.commit()
    conn.close()


# ============== 查询接口 ==============

def get_word(word_id):
    """获取单词详情"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM words WHERE id = ?', (word_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    word = dict(row)
    word['meanings'] = json.loads(word['meanings'] or '[]')
    word['frequency'] = json.loads(word['frequency'] or '{}')
    word['example'] = json.loads(word['example'] or '{}')
    word['derivatives'] = json.loads(word['derivatives'] or '[]')
    return word


def get_words_to_review(limit=10):
    """获取今日需要复习的单词"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT w.*, lr.status, lr.familiarity, lr.correct_count, lr.wrong_count
        FROM words w
        JOIN learning_records lr ON w.id = lr.word_id
        WHERE lr.status IN ('learning', 'review')
          AND (lr.next_review_at IS NULL OR lr.next_review_at <= datetime('now'))
        ORDER BY lr.familiarity ASC, lr.next_review_at ASC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    words = []
    for row in rows:
        word = dict(row)
        word['meanings'] = json.loads(word['meanings'] or '[]')
        word['frequency'] = json.loads(word['frequency'] or '{}')
        word['example'] = json.loads(word['example'] or '{}')
        word['derivatives'] = json.loads(word['derivatives'] or '[]')
        words.append(word)

    return words


def get_new_words(book='cet6_core', limit=10, exclude_mastered=True):
    """获取新单词"""
    conn = get_db()
    cursor = conn.cursor()

    if exclude_mastered:
        cursor.execute('''
            SELECT w.* FROM words w
            LEFT JOIN learning_records lr ON w.id = lr.word_id
            WHERE w.book = ?
              AND (lr.status IS NULL OR lr.status = 'new')
            ORDER BY w.id ASC
            LIMIT ?
        ''', (book, limit))
    else:
        cursor.execute('''
            SELECT w.* FROM words w
            WHERE w.book = ?
            ORDER BY w.id ASC
            LIMIT ?
        ''', (book, limit))

    rows = cursor.fetchall()
    conn.close()

    words = []
    for row in rows:
        word = dict(row)
        word['meanings'] = json.loads(word['meanings'] or '[]')
        word['frequency'] = json.loads(word['frequency'] or '{}')
        word['example'] = json.loads(word['example'] or '{}')
        word['derivatives'] = json.loads(word['derivatives'] or '[]')
        words.append(word)

    return words


def get_stats():
    """获取学习统计"""
    conn = get_db()
    cursor = conn.cursor()

    # 总词汇量统计
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'mastered' THEN 1 ELSE 0 END) as mastered,
            SUM(CASE WHEN status = 'review' THEN 1 ELSE 0 END) as reviewing,
            SUM(CASE WHEN status = 'learning' THEN 1 ELSE 0 END) as learning,
            SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) as new
        FROM learning_records
    ''')
    word_stats = dict(cursor.fetchone())

    # 今日统计
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT * FROM daily_stats WHERE date = ?', (today,))
    today_stats = cursor.fetchone()
    today_stats = dict(today_stats) if today_stats else {
        'date': today, 'new_learned': 0, 'reviewed': 0,
        'correct_count': 0, 'wrong_count': 0, 'streak': 0
    }

    # 最近7天数据（用于记忆曲线图）
    cursor.execute('''
        SELECT date, reviewed, correct_count, wrong_count
        FROM daily_stats
        ORDER BY date DESC LIMIT 7
    ''')
    recent_days = [dict(row) for row in cursor.fetchall()]

    # 薄弱词汇 TOP5
    cursor.execute('''
        SELECT w.word, lr.wrong_count, lr.familiarity
        FROM words w
        JOIN learning_records lr ON w.id = lr.word_id
        WHERE lr.wrong_count > 0
        ORDER BY lr.wrong_count DESC, lr.familiarity ASC
        LIMIT 5
    ''')
    weak_words = [dict(row) for row in cursor.fetchall()]

    # 学习日历（最近30天）
    cursor.execute('''
        SELECT date, reviewed FROM daily_stats
        WHERE date >= date('now', '-30 days')
        ORDER BY date ASC
    ''')
    calendar = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        'words': word_stats,
        'today': today_stats,
        'recent_days': recent_days,
        'weak_words': weak_words,
        'calendar': calendar
    }


def get_weak_words_for_spelling(limit=10):
    """获取需要拼写训练的薄弱词汇"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT w.*, lr.wrong_count, lr.familiarity
        FROM words w
        JOIN learning_records lr ON w.id = lr.word_id
        WHERE lr.wrong_count > 0 OR lr.familiarity < 50
        ORDER BY lr.wrong_count DESC, lr.familiarity ASC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    words = []
    for row in rows:
        word = dict(row)
        word['meanings'] = json.loads(word['meanings'] or '[]')
        word['frequency'] = json.loads(word['frequency'] or '{}')
        word['example'] = json.loads(word['example'] or '{}')
        word['derivatives'] = json.loads(word['derivatives'] or '[]')
        words.append(word)

    return words


def get_wrong_words(period='all', limit=50):
    """获取错题列表
    period: 'today' / 'week' / 'all'
    """
    conn = get_db()
    cursor = conn.cursor()

    time_filter = ''
    if period == 'today':
        time_filter = " AND date(s.created_at) = date('now')"
    elif period == 'week':
        time_filter = " AND s.created_at >= datetime('now', '-7 days')"

    cursor.execute(f'''
        SELECT w.*, lr.wrong_count, lr.correct_count, lr.familiarity, lr.status,
               COUNT(s.id) as recent_wrong_count,
               MAX(s.created_at) as last_wrong_at
        FROM words w
        JOIN learning_records lr ON w.id = lr.word_id
        JOIN study_logs s ON w.id = s.word_id AND s.result = 'wrong'
        WHERE lr.wrong_count > 0 {time_filter}
        GROUP BY w.id
        ORDER BY lr.wrong_count DESC, lr.familiarity ASC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    words = []
    for row in rows:
        word = dict(row)
        word['meanings'] = json.loads(word['meanings'] or '[]')
        word['frequency'] = json.loads(word['frequency'] or '{}')
        word['example'] = json.loads(word['example'] or '{}')
        word['derivatives'] = json.loads(word['derivatives'] or '[]')
        words.append(word)

    return words


def get_wrong_words_stats():
    """获取错题统计摘要"""
    conn = get_db()
    cursor = conn.cursor()

    # 总错题数
    cursor.execute('''
        SELECT COUNT(DISTINCT word_id) as total_wrong,
               SUM(wrong_count) as total_wrong_count
        FROM learning_records WHERE wrong_count > 0
    ''')
    row = cursor.fetchone()
    total_wrong = row['total_wrong'] or 0
    total_wrong_count = row['total_wrong_count'] or 0

    # 今日错题数
    cursor.execute('''
        SELECT COUNT(DISTINCT word_id) as today_wrong
        FROM study_logs
        WHERE result = 'wrong' AND date(created_at) = date('now')
    ''')
    today_wrong = cursor.fetchone()['today_wrong'] or 0

    # 本周错题数
    cursor.execute('''
        SELECT COUNT(DISTINCT word_id) as week_wrong
        FROM study_logs
        WHERE result = 'wrong' AND created_at >= datetime('now', '-7 days')
    ''')
    week_wrong = cursor.fetchone()['week_wrong'] or 0

    # 已攻克（曾经错但现在 mastered）
    cursor.execute('''
        SELECT COUNT(*) as conquered
        FROM learning_records
        WHERE wrong_count > 0 AND status = 'mastered'
    ''')
    conquered = cursor.fetchone()['conquered'] or 0

    conn.close()

    return {
        'total_wrong': total_wrong,
        'total_wrong_count': total_wrong_count,
        'today_wrong': today_wrong,
        'week_wrong': week_wrong,
        'conquered': conquered,
    }


# ============== 初始化 ==============

def setup():
    """初始化数据库并加载数据"""
    init_db()
    load_words_from_json()
    print("[Setup] Database initialized and words loaded.")


if __name__ == '__main__':
    setup()
