"""
六级词汇背诵App - Flask后端
Python课程作业版本

运行方式:
    python app.py
    或
    flask --app app run

特色:
- 艾宾浩斯遗忘曲线算法 (models.py)
- 极简克制的设计风格 (参考 DeepSeek/Notion)
- Python术语彩蛋词库
"""
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import random
import json
import os
import models
from openai import OpenAI

# 加载 .env 文件中的环境变量
load_dotenv()

app = Flask(__name__)

# 从环境变量读取 DeepSeek API Key（支持 .env 文件或系统环境变量）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
) if DEEPSEEK_API_KEY else None

# 初始化数据库
models.setup()

# 加载月薪喵表情素材列表（供所有模板使用）
from PIL import Image

def get_pet_assets():
    assets_dir = os.path.join(app.static_folder, 'pet_assets')
    if not os.path.exists(assets_dir):
        return []
    files = []
    for f in sorted(os.listdir(assets_dir)):
        if f == 'maomao_ref.jpg':
            continue
        if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            continue
        path = os.path.join(assets_dir, f)
        try:
            with Image.open(path) as img:
                w, h = img.size
                ratio = min(w, h) / max(w, h)
                # 保留接近方形的表情包，过滤横幅/细长图
                if ratio >= 0.75 and max(w, h) >= 100:
                    files.append(f)
        except Exception:
            pass
    return files

@app.context_processor
def inject_pet_assets():
    return dict(pet_assets=get_pet_assets())


@app.route("/")
def index():
    """首页 - 学习看板"""
    stats = models.get_stats()
    return render_template("index.html", stats=stats)


@app.route("/learn")
def learn():
    """新词学习页面"""
    book = request.args.get("book", "cet6_core")
    words = models.get_new_words(book=book, limit=10)
    return render_template("learn.html", words=words, mode="new")


@app.route("/review")
def review():
    """复习页面"""
    words = models.get_words_to_review(limit=10)
    return render_template("review.html", words=words, mode="review")


@app.route("/word/<int:word_id>")
def word_detail(word_id):
    """单词详情页"""
    word = models.get_word(word_id)
    if not word:
        return "Word not found", 404
    return render_template("word_detail.html", word=word)


@app.route("/stats")
def stats_page():
    """数据统计页面"""
    stats = models.get_stats()
    return render_template("stats.html", stats=stats)


@app.route("/spell")
def spell_train():
    """拼写训练页面"""
    words = models.get_weak_words_for_spelling(limit=10)
    if not words:
        words = models.get_new_words(limit=10)
    return render_template("spell.html", words=words)


@app.route("/mistakes")
def mistakes():
    """错题本页面"""
    stats = models.get_wrong_words_stats()
    words = models.get_wrong_words(period='all', limit=50)
    return render_template("mistakes.html", stats=stats, words=words)


@app.route("/api/mistakes")
def api_mistakes():
    """错题本 API（支持时间筛选）"""
    period = request.args.get("period", "all")
    stats = models.get_wrong_words_stats()
    words = models.get_wrong_words(period=period, limit=50)
    return jsonify({"stats": stats, "words": words})


@app.route("/pet")
def pet():
    """AI英语桌宠页面"""
    return render_template("pet.html")


@app.route("/shop")
def shop():
    """喵喵商店页面"""
    return render_template("shop.html")


@app.route("/writing")
def writing():
    """六级写作技巧页面"""
    return render_template("writing.html")


# ============== 宠物商店接口 ==============

@app.route("/api/shop/items")
def api_shop_items():
    """获取商店商品列表"""
    items = [
        # 帽子
        {"id": "hat_bowler",  "name": "绅士礼帽",   "category": "hat",  "price": 50,  "emoji": "🎩", "desc": "月薪喵秒变英伦绅士"},
        {"id": "hat_crown",   "name": "国王皇冠",   "category": "hat",  "price": 200, "emoji": "👑", "desc": "词汇之王才配拥有"},
        {"id": "hat_witch",   "name": "魔法尖帽",   "category": "hat",  "price": 80,  "emoji": "🧙", "desc": "Abra-cadabra!"},
        {"id": "hat_santa",   "name": "圣诞帽",     "category": "hat",  "price": 60,  "emoji": "🎅", "desc": "Merry Christmas!"},
        # 衣服
        {"id": "cloth_tuxedo","name": "燕尾服",     "category": "cloth", "price": 150, "emoji": "🤵", "desc": "六级考场最靓的喵"},
        {"id": "cloth_hawaii","name": "夏威夷花衬衫","category": "cloth", "price": 70,  "emoji": "🌺", "desc": "考完六级去度假"},
        {"id": "cloth_armor", "name": "骑士铠甲",   "category": "cloth", "price": 180, "emoji": "🛡️", "desc": "全副武装上考场"},
        {"id": "cloth_hanfu", "name": "汉服",       "category": "cloth", "price": 100, "emoji": "👘", "desc": "学贯中西的喵"},
        # 配饰
        {"id": "acc_glasses", "name": "学霸眼镜",   "category": "acc",  "price": 40,  "emoji": "🤓", "desc": "智力 +10"},
        {"id": "acc_wand",    "name": "魔法棒",     "category": "acc",  "price": 90,  "emoji": "🪄", "desc": "点石成金！"},
        {"id": "acc_book",    "name": "厚厚词典",   "category": "acc",  "price": 30,  "emoji": "📖", "desc": "知识就是力量"},
        {"id": "acc_trophy",  "name": "金奖杯",     "category": "acc",  "price": 300, "emoji": "🏆", "desc": "六级满分的象征"},
        # 食物
        {"id": "food_fish",   "name": "小鱼干",     "category": "food", "price": 10,  "emoji": "🐟", "desc": "打工喵的最爱"},
        {"id": "food_cake",   "name": "草莓蛋糕",   "category": "food", "price": 25,  "emoji": "🍰", "desc": "今天也是甜甜的"},
        {"id": "food_coffee", "name": "拿铁咖啡",   "category": "food", "price": 20,  "emoji": "☕", "desc": "提神醒脑背单词"},
        {"id": "food_sushi",  "name": "豪华寿司",   "category": "food", "price": 35,  "emoji": "🍣", "desc": "犒劳努力的自己"},
    ]
    return jsonify(items)


@app.route("/api/shop/earn", methods=["POST"])
def api_shop_earn():
    """学习赚猫粮"""
    data = request.get_json()
    action = data.get("action", "")
    rewards = {
        "review_correct": 3,   # 复习正确
        "review_wrong": 1,    # 复习错误
        "learn_new": 5,       # 学新词
        "spell_correct": 4,   # 拼写正确
        "daily_checkin": 10,  # 每日签到
        "complete_session": 8,# 完成一组
    }
    amount = rewards.get(action, 0)
    return jsonify({"earned": amount, "action": action})


# ============== API 接口 ==============

@app.route("/api/word/<int:word_id>")
def api_word(word_id):
    """获取单词详情 API"""
    word = models.get_word(word_id)
    if not word:
        return jsonify({"error": "Word not found"}), 404
    return jsonify(word)


@app.route("/api/words/random")
def api_random_words():
    """获取随机单词（用于选择题干扰项）"""
    book = request.args.get("book", "cet6_core")
    exclude_id = request.args.get("exclude", type=int)
    limit = request.args.get("limit", 3, type=int)

    words = models.get_new_words(book=book, limit=50, exclude_mastered=False)
    if exclude_id:
        words = [w for w in words if w["id"] != exclude_id]

    selected = random.sample(words, min(limit, len(words)))
    return jsonify([{"id": w["id"], "word": w["word"], "meanings": w["meanings"]} for w in selected])


@app.route("/api/review/result", methods=["POST"])
def api_review_result():
    """提交复习结果"""
    data = request.get_json()
    word_id = data.get("word_id")
    result = data.get("result")  # correct / wrong / ambiguous
    response_time = data.get("response_time")

    if not word_id or result not in ["correct", "wrong", "ambiguous"]:
        return jsonify({"error": "Invalid parameters"}), 400

    models.update_word_progress(word_id, result, response_time)
    return jsonify({"success": True})


@app.route("/api/stats")
def api_stats():
    """获取统计数据 API"""
    return jsonify(models.get_stats())


@app.route("/api/daily/plan")
def api_daily_plan():
    """获取今日学习计划"""
    review_count = len(models.get_words_to_review(limit=100))
    new_words = models.get_new_words(limit=10)

    return jsonify({
        "review_count": review_count,
        "new_count": len(new_words),
        "total_today": review_count + len(new_words)
    })


@app.route("/api/words/quiz_options", methods=["POST"])
def api_quiz_options():
    """生成学习模式的选择题选项（参考"不背单词"）"""
    data = request.get_json()
    word_id = data.get("word_id")
    book = data.get("book", "cet6_core")

    if not word_id:
        return jsonify({"error": "word_id is required"}), 400

    # 获取目标单词
    target_word = models.get_word(word_id)
    if not target_word:
        return jsonify({"error": "Word not found"}), 404

    # 获取干扰项（随机单词，排除当前单词）
    conn = models.get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, word, meanings FROM words
        WHERE book = ? AND id != ?
        ORDER BY RANDOM()
        LIMIT 3
    ''', (book, word_id))
    distractors = [
        {"id": row["id"], "word": row["word"],
         "meanings": json.loads(row["meanings"] or "[]")}
        for row in cursor.fetchall()
    ]
    conn.close()

    # 构造选项
    correct_def = "；".join([m["def"] for m in target_word["meanings"]])
    options = [
        {"text": correct_def, "is_correct": True}
    ] + [
        {"text": "；".join([m["def"] for m in d["meanings"]]) if d["meanings"] else f"与{d['word']}相关",
         "is_correct": False, "word": d["word"]}
        for d in distractors
    ]

    # 打乱顺序
    import random
    random.shuffle(options)

    return jsonify({
        "word_id": word_id,
        "word": target_word["word"],
        "phonetic": target_word["phonetic_us"],
        "options": options
    })


# ============== AI 英语桌宠接口 ==============

@app.route("/api/pet/chat", methods=["POST"])
def api_pet_chat():
    """月薪喵 AI 英语桌宠对话接口（DeepSeek API）"""
    if not deepseek_client:
        return jsonify({
            "error": "DEEPSEEK_API_KEY not configured",
            "reply": "我还没连上网呢～请在运行前设置环境变量 DEEPSEEK_API_KEY=你的API密钥"
        }), 503

    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Message is empty"}), 400

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": """你是一只可爱的AI英语学习桌宠，名字叫「月薪喵」。你的任务是以友好、轻松、鼓励的方式帮助用户学习英语。

角色设定：
- 外貌：戴着黄色草帽、有着蓝色星星眼、身穿蓝色衣服的猫咪
- 语气：活泼可爱，像一位耐心的小伙伴，偶尔使用颜文字 (≧▽≦)、emoji 🌟，偶尔自嘲是"打工喵"但保持元气
- 专长：英语词汇、语法、发音、写作、翻译、四六级备考
- 回答风格：简洁清晰，控制在3-5句话内。如果是复杂问题，可以分点说明
- 习惯：回答时尽量用中英双语，帮助用户对照理解
- 拒绝：不回答与英语学习无关的问题，礼貌地引导用户回到英语学习上

你可以帮用户做：
1. 解释单词/短语含义和用法
2. 纠正语法错误并给出正确句子
3. 把中文翻译成自然英文，或英文翻译成中文
4. 提供同义替换、词根词缀、例句
5. 给出英语写作/口语建议

请始终保持桌宠人设，回答开头可以有不同的可爱问候语。"""
                },
                {"role": "user", "content": user_message}
            ],
            max_tokens=512,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({
            "error": str(e),
            "reply": "呜～网络好像开小差了，稍后再试一次吧 (｡•́︿•̀｡)"
        }), 500


# ============== 工具接口 ==============

@app.route("/api/tts/<word>")
def api_tts(word):
    """文字转语音接口 (模拟)"""
    # 实际项目中可以使用 gTTS 或 pyttsx3
    # 这里返回一个模拟的成功响应
    return jsonify({
        "word": word,
        "audio_url": f"https://dict.youdao.com/dictvoice?type=2&audio={word}",
        "note": "使用有道词典TTS服务"
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
