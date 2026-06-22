import asyncio, json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "parser"))  # "job_parser" → "parser"

from services.parsers.parser_router import parse_job
# 공고 url
URL = "https://m.jobkorea.co.kr/info/app_down.asp?Gno=49416174"

async def main():
    print(f"파싱 중... {URL}\n")
    result = await parse_job(URL)
    d = result.to_dict()

    if d["error"]:
        print(f"오류: {d['error']}")
        return

    print(f"제목     : {d['title']}")
    print(f"회사명   : {d['company']}")
    print(f"구분     : {d['job_type']}")
    # print(f"\n담당업무 ({len(d['tasks'])}개):")
    # for t in d["tasks"]:
    #     print(f"  {t}")
    print(f"\n기술스택 ({len(d['tech_stack'])}개):")
    print(f"  {', '.join(d['tech_stack'])}")
    # result = await parse_job(URL)

    # print("RESULT =", result.tech_stack)

    result = await parse_job(URL)

    print("RESULT ID =", id(result))
    print("RESULT =", result.tech_stack)

    d = result.to_dict()

    print("DICT =", d["tech_stack"])

asyncio.run(main())