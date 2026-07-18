from llm.llm_setup import get_llm
from llm.prompts import ANSWER_PROMPT

def generate_answer (query: str, chunks: list) -> str:

    context = "\n\n".join(chunk.page_content for chunk in chunks)

    prompt = ANSWER_PROMPT.format (context = context, question= query)


    llm = get_llm (temperature=0)

    response = llm.invoke(prompt)

    answer = response.content

    return answer


if __name__=="__main__":
    from agents.navigator_agent import navigator




    query = "my mother is 50 years old and she is having diabetes since last seven years. She is on oral hypoglycaemic drugs like glycomet gp 1 twice daily and vildagliptin 50 MG twice daily, but in the morning blood sugar level often remains increase what we could do to control that?"


    print ("Getting chunks from navigator\n")
    chunks = navigator(query)

    print ("\n Generating Answer...")
    answer = generate_answer(query,chunks)

    print ("\n=========Answer============")

    print (answer)



