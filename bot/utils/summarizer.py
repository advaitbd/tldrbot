import openai
import configparser

# Set API key
config = configparser.ConfigParser()
config.read("config.ini")
openai.api_key = config["OpenAI"]["api_key"]

def get_summary(result):
    # Define prompt 
    prompt = "Summarise this group chat that occurred on Telegram in a friendly banterful manner, making references to who said what " + result

    # Call API and receive response 
    generated = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"{prompt}"}])
    
    # # Extract summary text from response 
    # summary = generated.choices[0].text.strip()

    # # Parse and format summary as needed 
    # parsed_summary = json.loads(summary)

    # Output summary to console 
    return generated["choices"][0]["message"]["content"]