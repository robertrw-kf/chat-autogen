import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import openai
import os
import re
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from autogen import AssistantAgent, UserProxyAgent
import dummy
import time
import uuid
from PIL import Image

css = """
<style>
.stFrame {
    position: fixed;
    top: 0;
    left: 0;
    height: 100%;
    overflow-y: auto;
    background-color: #f0f0f0; /* Change this to the desired background color */
    width: 250px; /* Adjust the width as needed */
    padding: 20px; /* Adjust the padding as needed */
    box-shadow: 2px 0px 6px rgba(0, 0, 0, 0.1); /* Optional shadow effect */
}
</style>
"""
components.html(css, height=0)

try:
    load_dotenv()
except:
    raise Exception("Error loading .env file")

def load_dataset():
    
    return pd.read_csv(os.getenv("DATASET_PATH"))

def generate_random_filename(extension='.png'):
    """
    Generate a random filename with the given extension.

    Parameters:
    - extension (str): The file extension (e.g., '.txt').

    Returns:
    - str: A random filename with the specified extension.
    """
    random_filename = str(uuid.uuid4())
    if extension:
        random_filename += extension
    return random_filename

prompt_template = f""" You are an expert at writing python code to solve problems.
                        you have been provided with the file {os.getenv('DATASET_PATH')}, the file contains a tabular data
                        and below are the columns present
                        `{load_dataset().columns}`
                        Write valid python code to solve the questions asked you can use python data analysis 
                        libraries like pandas, numpy, matplotlib and more to solve the problem. Print the result 
                        to the user in a descriptive way and not in one word.
                        Return the code to the user, make sure the code does not contain
                        any errors. If the code is executed successfully reply `TERMINATE` and
                        terminate the chat immediately and do not ask the 
                        user for a confirmation to terminate
               """

config_list = [
    {
        "model": os.getenv("MODEL_NAME"),
        "api_key": os.getenv("OPENAI_API_KEY")
    }
]

llm_config = { 
    "seed": 42,
    "temperature": 0,
    "config_list": config_list,
    "timeout": 600, 
}

err_response = {'response': "Unable to process you request now. Please try again later.",
                    'type': 'str'}

assistant = AssistantAgent(name="coding_assistant",
                          llm_config=llm_config,
                          system_message=prompt_template)

user_proxy = UserProxyAgent(name="user_proxy",
                          human_input_mode="NEVER",
                          max_consecutive_auto_reply=3,
                          is_termination_msg=lambda msg: "TERMINATE" in msg["content"],
                          code_execution_config={
                               "work_dir": "coding",
                               "use_docker": False
                               },
                          system_message="""If the problem is solved respond TERMINATE"""
                          )

def extract_code(response):
    code_pattern = r"```(.*?)```"
    if re.findall(code_pattern, response, re.DOTALL):
        code_blocks = re.findall(code_pattern, response, re.DOTALL)
        formatted_code = "\n".join([line for line in code_blocks[0].split('\n')])
        return formatted_code



def chat(prompt):
    data = []
    try:
        user_proxy.initiate_chat(assistant, 
                                message = prompt)
        for k, v in user_proxy.chat_messages.items():
            for item in v:
                data.append({'Role': item['role'], 'Content': item['content']})
        for item in data:
            if (item['Role'] == 'assistant') and item['Content'].startswith('exitcode: 0 (execution succeeded)'):
                if 'Figure' in item['Content'].split('Code output:')[-1]:
                    raw_code = ', '.join(str(d) for d in data)
                    formatted_code = extract_code(raw_code)
                    if formatted_code is not None:
                        response = formatted_code
                        return {'response': response,
                                'type': 'code'}
                    else:
                        err_response
                else:
                    response = item['Content'].split('Code output:')[-1]
                    return {'response': response,
                            'type': 'str'}
    except Exception as e:
        if "RateLimitError" in str(e):
            for k, v in user_proxy.chat_messages.items():
                for item in v:
                    data.append({'Role': item['role'], 'Content': item['content']})
            for item in data:
                if (item['Role'] == 'assistant') and item['Content'].startswith('exitcode: 0 (execution succeeded)'):
                    response = item['Content'].split('Code output:')[-1]
                    break
            return {'response': response,
                    'type': 'str'}
        else:
            return err_response
        




def csv_analyzer_app():
    """Main Streamlit application for CSV analysis."""

    st.sidebar.title("FSBI Data Assistant")
    st.subheader('Chat with your data')
    df = load_dataset()
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question..."):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            response = chat(prompt)
            try:
                if response is not None:
                    print(response['response'])
                    if response['type'] == 'code':
                        print("Response type is code")
                        try:
                        # Making df available for execution in the context
                            exec(response['response'], globals(), {"df": df, "plt": plt})
                            fig = plt.gcf()  # Get current figure
                            # filename = generate_file_name()
                            # plt.savefig(f"temp/{filename}.png", format="png")
                            # st.session_state.plot_image_path = f"temp/{filename}.png"
                            # st.session_state.messages.append({"role": "assistant", "content": st.image(Image.open(f"temp/{filename}.png"))})
                            # st.session_state.response_map[len(st.session_state.messages)] = {'rsp_type': 'plot', 'path': f"temp/{filename}.png" }
                            # for key, value in st.session_state.response_map.items():
                            #     if value['rsp_type'] == 'plot':
                            #         # st.session_state.plot_image_path = value['path']
                            #         image = Image.open(value['path'])
                            #         st.session_state.messages[key-1]['content'] ==  st.image(image)
                        except Exception as e:
                            st.session_state.messages.append({"role": "assistant", "content": "Unable to process your request now, Please try again later"})
                    else:
                        for chunk in response['response'].split():
                            full_response += chunk + " "
                            time.sleep(0.10)
                            message_placeholder.markdown(full_response + "▌")
                        message_placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.session_state.messages.append({"role": "assistant", "content": "Unable to process your request now, Please try again later"})

if __name__ == "__main__":
    csv_analyzer_app()
