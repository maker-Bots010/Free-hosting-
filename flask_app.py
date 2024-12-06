from flask import Flask, request, render_template, jsonify, session, redirect, url_for
import os
import subprocess
import uuid
from threading import Thread

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_user_folder():
    user_id = session.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())
        session['user_id'] = user_id

    user_folder = os.path.join('uploads', user_id)

    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    return user_folder

processes = {}
output_logs = {}

def run_file_in_thread(filepath, filename):
    while True: 
        process = subprocess.Popen(
            ['python', filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes[filename] = process
        output_logs[filename] = []  

        while True:
            output = process.stdout.readline()
            if output == b'' and process.poll() is not None:
                break
            if output:
                output_logs[filename].append(output.decode().strip())  

        del processes[filename]
        print(f"{filename} has stopped. Restarting...")

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    user_folder = get_user_folder()

    if request.method == 'POST':
        files = request.files.getlist('files')
        uploaded_files = []
        for file in files:
            if file.filename == '':
                continue
            if file and file.filename.endswith('.py'):
                filepath = os.path.join(user_folder, file.filename)
                file.save(filepath)
                uploaded_files.append(file.filename)

        if uploaded_files:
            session['uploaded_files'] = session.get('uploaded_files', []) + uploaded_files
            return jsonify({"message": "Files uploaded successfully", "filenames": uploaded_files}), 200
        else:
            return jsonify({"error": "No valid files uploaded"}), 400

    files = os.listdir(user_folder)
    return render_template('index.html', files=files, uploaded_files=session.get('uploaded_files', []), processes=processes)

@app.route('/myfile', methods=['GET'])
def my_files():
    user_folder = get_user_folder()
    files = os.listdir(user_folder)  
    running_files = list(processes.keys()) 
    return render_template('myfile.html', files=files, running_files=running_files)

@app.route('/creatfile', methods=['GET', 'POST'])
def create_file():
    if request.method == 'POST':
        filename = request.form.get('filename')
        content = request.form.get('content') 
        user_folder = get_user_folder()
        filepath = os.path.join(user_folder, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)


        if 'uploaded_files' not in session:
            session['uploaded_files'] = []
        session['uploaded_files'].append(filename)

        return jsonify({"message": "File created successfully", "filename": filename}), 200

    return render_template('createfile.html') 

@app.route('/edit/<filename>', methods=['GET', 'POST'])
def edit_file(filename):
    """Edit the content of the specified Python file."""
    user_folder = get_user_folder()
    filepath = os.path.join(user_folder, filename)

    if request.method == 'POST':
        content = request.form.get('content')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return redirect(url_for('my_files')) 

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    return render_template('editfile.html', filename=filename, content=content)

@app.route('/run/<filename>', methods=['POST'])
def run_file(filename):
    user_folder = get_user_folder()
    filepath = os.path.join(user_folder, filename)

    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    if filename in processes:  
        return jsonify({"error": "File is already running"}), 400

    thread = Thread(target=run_file_in_thread, args=(filepath, filename))
    thread.start()
    return jsonify({"message": "File is running", "filename": filename}), 200

@app.route('/stop/<filename>', methods=['POST'])
def stop_file(filename):
    """Stop the running process for the specified file."""
    process = processes.get(filename)
    if process and process.poll() is None:
        process.terminate()
        return jsonify({"message": "Process terminated"}), 200

    return jsonify({"error": "Process not running"}), 404

@app.route('/restart/<filename>', methods=['POST'])
def restart_file(filename):
    """Restart the specified Python file."""
    stop_file(filename) 
    return run_file(filename)  

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    stop_file(filename)
    user_folder = get_user_folder()
    filepath = os.path.join(user_folder, filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        if filename in session.get('uploaded_files', []):
            session['uploaded_files'].remove(filename)
        return jsonify({"message": "File deleted successfully"}), 200

    return jsonify({"error": "File not found"}), 404

@app.route('/output/<filename>', methods=['GET'])
def get_output(filename):
    return jsonify({"logs": output_logs.get(filename, [])}), 200

@app.route('/terminal', methods=['POST'])
def run_terminal_command():
    command = request.form.get('command')
    if command:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        return jsonify({"stdout": stdout.decode(), "stderr": stderr.decode()}), 200

    return jsonify({"error": "No command provided"}), 400

if __name__ == '__main__':
    app.run(debug=True)