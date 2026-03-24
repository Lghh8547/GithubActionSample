# 安装依赖 pip3 install requests html5lib bs4 schedule
import os
import requests
import json
import re
from bs4 import BeautifulSoup

# 从测试号信息获取
appID = os.environ.get("APP_ID")
appSecret = os.environ.get("APP_SECRET")
# 收信人ID即 用户列表中的微信号
openId = os.environ.get("OPEN_ID")
# 天气预报模板ID
weather_template_id = os.environ.get("TEMPLATE_ID")
# 获取天气的城市（可配置）
weather_city = os.environ.get("WEATHER_CITY", "北京")  # 默认北京

def get_weather(my_city):
    urls = ["http://www.weather.com.cn/textFC/hb.shtml",
            "http://www.weather.com.cn/textFC/db.shtml",
            "http://www.weather.com.cn/textFC/hd.shtml",
            "http://www.weather.com.cn/textFC/hz.shtml",
            "http://www.weather.com.cn/textFC/hn.shtml",
            "http://www.weather.com.cn/textFC/xb.shtml",
            "http://www.weather.com.cn/textFC/xn.shtml"
            ]
    for url in urls:
        resp = requests.get(url)
        text = resp.content.decode("utf-8")
        soup = BeautifulSoup(text, 'html5lib')
        div_conMidtab = soup.find("div", class_="conMidtab")
        tables = div_conMidtab.find_all("table")
        for table in tables:
            trs = table.find_all("tr")[2:]
            for index, tr in enumerate(trs):
                tds = tr.find_all("td")
                # 这里倒着数，因为每个省会的td结构跟其他不一样
                city_td = tds[-8]
                this_city = list(city_td.stripped_strings)[0]
                if this_city == my_city:

                    high_temp_td = tds[-5]
                    low_temp_td = tds[-2]
                    weather_type_day_td = tds[-7]
                    weather_type_night_td = tds[-4]
                    wind_td_day = tds[-6]
                    wind_td_day_night = tds[-3]

                    high_temp = list(high_temp_td.stripped_strings)[0]
                    low_temp = list(low_temp_td.stripped_strings)[0]
                    weather_typ_day = list(weather_type_day_td.stripped_strings)[0]
                    weather_type_night = list(weather_type_night_td.stripped_strings)[0]

                    wind_day = list(wind_td_day.stripped_strings)[0] + list(wind_td_day.stripped_strings)[1]
                    wind_night = list(wind_td_day_night.stripped_strings)[0] + list(wind_td_day_night.stripped_strings)[1]

                    # 如果没有白天的数据就使用夜间的
                    temp = f"{low_temp}——{high_temp}摄氏度" if high_temp != "-" else f"{low_temp}摄氏度"
                    weather_typ = weather_typ_day if weather_typ_day != "-" else weather_type_night
                    wind = f"{wind_day}" if wind_day != "--" else f"{wind_night}"
                    return this_city, temp, weather_typ, wind


def get_access_token():
    # 获取access token的url
    url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={}&secret={}' \
        .format(appID.strip(), appSecret.strip())
    response = requests.get(url).json()
    print(response)
    access_token = response.get('access_token')
    return access_token


def get_ai_suggestions(weather_info):
    """
    基于天气信息获取国产AI穿衣和出行建议
    """
    city, temp, weather_type, wind = weather_info
    
    # 解析温度范围
    temp_match = re.search(r'(\d+)—(\d+)|(-?\d+)', temp)
    if temp_match:
        if temp_match.group(1) and temp_match.group(2):
            low_temp = int(temp_match.group(1))
            high_temp = int(temp_match.group(2))
        else:
            low_temp = high_temp = int(temp_match.group(3))
    else:
        low_temp = high_temp = 20  # 默认温度
    
    avg_temp = (low_temp + high_temp) / 2
    
    # 构建天气描述
    weather_desc = f"城市：{city}，温度：{temp}，天气：{weather_type}，风力：{wind}"
    
    # AI提示词
    prompt = f"""
基于以下天气信息，请提供简洁实用的穿衣建议和出行建议：

{weather_desc}
平均温度：{avg_temp:.1f}°C

请分别回答：
1. 穿衣建议：（具体建议，如穿什么类型的衣服、材质、厚度等）
2. 出行建议：（是否适合出行、注意事项、携带物品等）

要求：
- 建议要简洁明了，每条不超过50字
- 语言要亲切自然
- 针对当前天气条件给出实用建议
- 格式：穿衣建议：XXX | 出行建议：XXX
"""
    
    try:
        # 尝试使用百度文心一言
        if os.environ.get("BAIDU_API_KEY") and os.environ.get("BAIDU_SECRET_KEY"):
            return get_baidu_suggestions(prompt)
        # 尝试使用阿里通义千问
        elif os.environ.get("DASHSCOPE_API_KEY"):
            return get_qwen_suggestions(prompt)
        else:
            print("未配置国产AI API，使用备用规则建议")
            return get_fallback_suggestions(avg_temp, weather_type, wind)
        
    except Exception as e:
        print(f"国产AI建议获取失败: {e}")
        # 备用规则建议
        return get_fallback_suggestions(avg_temp, weather_type, wind)


def get_baidu_suggestions(prompt):
    """
    使用百度文心一言获取建议
    """
    import requests
    import time
    
    # 获取access_token
    api_key = os.environ.get("BAIDU_API_KEY")
    secret_key = os.environ.get("BAIDU_SECRET_KEY")
    
    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    token_response = requests.get(token_url)
    access_token = token_response.json().get("access_token")
    
    if not access_token:
        raise Exception("百度API token获取失败")
    
    # 调用文心一言
    url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/eb-instant?access_token={access_token}"
    
    payload = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_output_tokens": 150
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    
    if "result" in result:
        return result["result"].strip()
    else:
        raise Exception(f"百度API错误: {result}")


def get_qwen_suggestions(prompt):
    """
    使用阿里通义千问获取建议
    """
    try:
        from dashscope import Generation
        import dashscope
        
        dashscope.api_key = os.environ.get("DASHSCOPE_API_KEY")
        
        response = Generation.call(
            model="qwen-turbo",
            prompt=prompt,
            max_tokens=150,
            temperature=0.7
        )
        
        if response.status_code == 200:
            return response.output.text.strip()
        else:
            raise Exception(f"通义千问API错误: {response}")
            
    except ImportError:
        print("需要安装dashscope: pip install dashscope")
        raise


def get_fallback_suggestions(avg_temp, weather_type, wind):
    """
    备用规则建议（当AI不可用时）
    """
    # 穿衣建议
    if avg_temp >= 30:
        clothing = "穿短袖、短裤、凉鞋，注意防晒"
    elif avg_temp >= 20:
        clothing = "穿长袖、长裤，可备薄外套"
    elif avg_temp >= 10:
        clothing = "穿毛衣、外套，注意保暖"
    else:
        clothing = "穿羽绒服、厚外套，做好防寒"
    
    # 出行建议
    if "雨" in weather_type or "雪" in weather_type:
        travel = "携带雨具，注意路滑，谨慎出行"
    elif "霾" in weather_type or "雾" in weather_type:
        travel = "减少外出，佩戴口罩，注意安全"
    elif avg_temp >= 35:
        travel = "避免高温时段外出，多补水"
    elif avg_temp <= -10:
        travel = "减少不必要外出，注意防冻"
    else:
        travel = "适合出行，注意天气变化"
    
    return f"穿衣建议：{clothing} | 出行建议：{travel}"


def get_daily_love():
    # 每日一句情话
    url = "https://api.lovelive.tools/api/SweetNothings/Serialization/Json"
    r = requests.get(url)
    all_dict = json.loads(r.text)
    sentence = all_dict['returnObj'][0]
    daily_love = sentence
    return daily_love


def send_weather(access_token, weather):
    # touser 就是 openID
    # template_id 就是模板ID
    # url 就是点击模板跳转的url
    # data就按这种格式写，time和text就是之前{{time.DATA}}中的那个time，value就是你要替换DATA的值

    import datetime
    today = datetime.date.today()
    
    # 获取AI建议和情话
    ai_suggestions = get_ai_suggestions(weather)
    daily_love = get_daily_love()
    
    # 组合消息：AI建议 + 情话
    combined_message = f"{ai_suggestions}\n💕 {daily_love}"

    body = {
        "touser": openId.strip(),
        "template_id": weather_template_id.strip(),
        "url": "https://weixin.qq.com",
        "data": {
            "date": {
                "value": today.strftime("%Y年%m月%d日")
            },
            "region": {
                "value": weather[0]
            },
            "weather": {
                "value": weather[2]
            },
            "temp": {
                "value": weather[1]
            },
            "today_note": {
                "value": combined_message
            }
        }
    }
    url = 'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={}'.format(access_token)
    print(requests.post(url, json.dumps(body)).text)



def weather_report(this_city):
    # 1.获取access_token
    access_token = get_access_token()
    # 2. 获取天气
    weather = get_weather(this_city)
    print(f"天气信息： {weather}")
    # 3. 发送消息
    send_weather(access_token, weather)



if __name__ == '__main__':
    weather_report(weather_city)
