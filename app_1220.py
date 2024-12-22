from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import random
import requests
import time
import openai 
from flask_cors import CORS

app = Flask(__name__, template_folder='templates')
app.secret_key = 'a_strong_secret_key_here'  # Replace with a secure key
 
 # OpenAI API Key
API_KEY = "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"
EXTERNAL_API_URL = "https://api.openai.com/v1/chat/completions"

# Global Variables
chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters, hint_image = None, None, None, None, None, None


# Function to load characters
def load_characters_from_file(file_path="characters.json"):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading characters: {str(e)}")
        return {"error": str(e)}


def generate_murder_mystery():
    global chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters

    characters = load_characters_from_file()
    if "error" in characters:
        return "Error loading characters."

    # Prepare GPT prompt
    character_list_str = "\n".join(
        [f"{key}: {value['Name']}, Items: {', '.join(value['Items'])}" for key, value in characters.items()]
    )
    prompt = f"""
    You are a game master in a murder mystery game. Here is a list of characters and the items they possess:

    {character_list_str}

    1. Select one murderer and one item (murder weapon) that belongs to them.
    2. Select one victim.
    3. Provide a concise hint in Korean to help players identify the murderer.
    4. Select four other normal characters who are not the murderer or victim.

    Provide your output in the following format:
    Murderer: [Character Name]
    Murder Weapon: [Item]
    Hint: [Your Hint]
    Victim: [Character Name]
    Others: [Character Name 1, Character Name 2, Character Name 3, Character Name 4]
    """
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400
    }

    try:
        response = requests.post(EXTERNAL_API_URL, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            decision = result['choices'][0]['message']['content']

            # Parse GPT response
            print("GPT Response:", decision)  # Debugging log
            lines = decision.split("\n")
            for line in lines:
                if line.startswith("Murderer:"):
                    chosen_murderer = line.split(":")[1].strip()
                elif line.startswith("Murder Weapon:"):
                    chosen_item = line.split(":")[1].strip()
                elif line.startswith("Hint:"):
                    chosen_hint = line.split(":")[1].strip()
                elif line.startswith("Victim:"):
                    chosen_victim = line.split(":")[1].strip()
                elif line.startswith("Others:"):
                    normal_characters = line.split(":")[1].strip().strip("[]").split(", ")
            return None  # No errors
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return "Error interacting with GPT API."
    except Exception as e:
        print(f"Exception during GPT interaction: {e}")
        return "Exception during GPT interaction."


def generate_new_hint(murderer_name):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
    You are a game master in a murder mystery game. The murderer is '{murderer_name}'.
    Provide a unique and creative hint in Korean that can help players identify the murderer.
    Ensure the hint is concise, intriguing, and ties the murderer and item together in 20 words.
    """
    data = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200
    }
    response = requests.post(EXTERNAL_API_URL, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        print(f"Error generating hint: {response.status_code} - {response.text}")
        return "새로운 힌트를 가져오는 중 오류가 발생했습니다. 다시 시도해 주세요!"


def generate_hint_image(victim, weapon):
    try:
        openai.api_key = API_KEY
        prompt = (
            f"A mysterious and dramatic crime scene where {victim} lies dead on the floor. "
            f"The murder weapon, a {weapon}, is prominently visible near the body. "
            "The room has large windows revealing a private island setting, and the atmosphere is eerie and dark."
        )
        response = openai.Image.create(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            n=1
        )
        return response['data'][0]['url']
    except Exception as e:
        print(f"Error generating hint image: {str(e)}")
        return "static/default_hint.webp"  # Use fallback image

@app.route('/')
def index():
    # Reset session variables or game state if needed
    session['failed_attempts'] = 0
    global chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters, hint_image
    chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters, hint_image = None, None, None, None, None, None
    return render_template('index.html')


@app.route('/story', methods=['GET', 'POST'])
def story():
    global chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters

    if not all([chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters]):
        characters = load_characters_from_file()
        if "error" in characters:
            return jsonify({'message': 'Error loading characters.', 'error': characters['error']}), 500

    return render_template(
        'story.html'
    )

@app.route('/hint', methods=['GET'])
def hint():
    global chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters, hint_image

    regenerate_hint = request.args.get('regenerate_hint', 'false').lower() == 'true'

    if regenerate_hint or not all([chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters, hint_image]):
        if not all([chosen_murderer, chosen_item, chosen_hint, chosen_victim, normal_characters]):
            print("Generating murder mystery data...")
            error = generate_murder_mystery()
            if error:
                print(f"Error generating murder mystery: {error}")
                return jsonify({"message": error}), 500

        print("Regenerating hint...")
        chosen_hint = generate_new_hint(chosen_murderer)
        hint_image = generate_hint_image(chosen_victim, chosen_item)

    return render_template(
        'hint.html',
        hint=chosen_hint,
        victim=chosen_victim,
        hint_image=hint_image
    )

@app.route('/result', methods=['POST'])
def result():
    global chosen_murderer, chosen_item

    guessed_character = request.form.get('character')
    guessed_item = request.form.get('item')

    # Initialize failed_attempts in session if not already set
    if 'failed_attempts' not in session:
        session['failed_attempts'] = 0

    success = guessed_character == chosen_murderer and guessed_item == chosen_item
    if success:
        session['failed_attempts'] = 0  # Reset attempts on success
        return render_template('result.html', success=True, remaining_lives=None)
    else:
        # Increment failed_attempts
        session['failed_attempts'] += 1
        remaining_lives = 3 - session['failed_attempts']

        if session['failed_attempts'] >= 3:
            # Failed all attempts, restart or show fail result
            return render_template('result.html', success=False, remaining_lives=0, restart=True)
        else:
            # Show fail result with remaining lives
            return render_template('result.html', success=False, remaining_lives=remaining_lives, restart=False)

@app.route('/choose_character', methods=['GET'])
def choose_character():
    global chosen_murderer, chosen_victim, normal_characters

    # Ensure story data exists
    if not all([chosen_murderer, chosen_victim, normal_characters]):
        print("Error: Story data is missing. Redirecting to story.")
        return redirect(url_for('story'))

    characters = load_characters_from_file()
    if "error" in characters:
        return jsonify({'message': 'Error loading characters.', 'error': characters['error']}), 500

    # Ensure murderer, victim, and others exist in the character list
    valid_names = [char["Name"] for char in characters.values()]
    selected_names = [chosen_murderer, chosen_victim] + normal_characters

    # Filter out invalid names
    selected_names = [name for name in selected_names if name in valid_names]

    # Filter selected characters
    selected_characters = {key: value for key, value in characters.items() if value["Name"] in selected_names}

    # Validate the total count
    if len(selected_characters) != 6:
        print("Error: Not enough valid characters selected.")
        print("Valid characters:", selected_names)
        print("Selected characters:", selected_characters)
        return jsonify({'message': 'Error: Not enough characters selected.'}), 500

    return render_template('choose_characters.html', characters=selected_characters)

@app.route('/choose_item/<character>', methods=['GET', 'POST'])
def choose_item(character):
    characters = load_characters_from_file()
    if character not in characters:
        return "Character not found", 404

    selected_character = characters[character]
    items = selected_character["Items"]
    item_images = selected_character.get("ItemImages", {})

    if request.method == 'POST':
        selected_item = request.form.get('item')
        if selected_item:
            return redirect(url_for('result', character=character, item=selected_item))
        else:
            return "No item selected", 400

    return render_template(
        'choose_item.html',
        character=selected_character["Name"],
        items=items,
        item_images=item_images
    )

characters = load_characters_from_file()

@app.route('/character/<character_key>', methods=['GET'])
def character_page(character_key):
    if character_key not in characters:
        return render_template('404.html', message=f"Character {character_key} not found."), 404

    selected_character = characters[character_key]
    print(f"Video path for {character_key}: {selected_character.get('Video', 'static/default.mp4')}")  # Debugging
    alibi = generate_character_alibi(selected_character["Name"])
    return render_template('character.html', character=selected_character, alibi=alibi)


def generate_character_alibi(character_name):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
    You are the character '{character_name}' which has been questioned.
    Provide your alibi in Korean as the character, explaining your whereabouts and actions at the time of the murder.
    Make the alibi intriguing but slightly ambiguous in 15 words.
    """
    data = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200
    }
    response = requests.post(EXTERNAL_API_URL, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        print(f"Error generating alibi: {response.status_code} - {response.text}")
        return "알리바이를 생성하는 중 오류가 발생했습니다. 다시 시도해주세요."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
#a faire : faire changer le hint quand la personne s'est trompée , parce que le meme hint est reproduit (text et photo)