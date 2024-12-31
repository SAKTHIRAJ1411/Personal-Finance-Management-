from flask import Flask, render_template, request, redirect, url_for, session, flash,jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime,date
import re,logging
from decimal import Decimal


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL connection configuration
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',  
        database='financial_db'  
    )

# ----------------------- Routes -----------------------

# Login Route
@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()

        if user:
            session['loggedin'] = True
            session['userid'] = user['userid']
            session['name'] = user['name']
            session['email'] = user['email']
            return redirect(url_for('dashboard'))  # Redirect to dashboard route
        else:
            message = 'Invalid email or password!'
        cursor.close()
        connection.close()

    return render_template('login.html', message=message)

# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    if request.method == 'POST' and all(k in request.form for k in ['name', 'password', 'email']):
        userName = request.form['name']
        password = request.form['password']
        email = request.form['email']

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute('SELECT * FROM user WHERE email = %s', (email,))
        account = cursor.fetchone()

        if account:
            message = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            message = 'Invalid email address!'
        elif not userName or not password or not email:
            message = 'Please fill out the form!'
        else:
            cursor.execute('INSERT INTO user (name, email, password) VALUES (%s, %s, %s)', (userName, email, password))
            connection.commit()
            message = 'You have successfully registered!'

        cursor.close()
        connection.close()
    return render_template('register.html', message=message)

# Dashboard Route
@app.route('/dashboard')
def dashboard():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    if 'loggedin' in session:  
        current_date = datetime.today().strftime("%Y-%m-%d")
        username = session['name']
        accounts = fetch_accounts()
        bills = fetch_bills()
        transactions = fetch_transactions()
        expenses=fetch_expense()

        query_due_today = """
        SELECT * FROM bills 
    WHERE due_date = %s AND status = %s"""
        cursor.execute(query_due_today, (current_date,'Pending'))
        due_today = cursor.fetchall()


        cursor.execute("""
            SELECT * FROM bills ORDER BY due_date ASC
        """)
        all_bills = cursor.fetchall()

        # Separate Pending and Paid bills for better
        pending_bills = [bill for bill in all_bills if bill['status'] == 'Pending']
        paid_bills = [bill for bill in all_bills if bill['status'] == 'Paid']


    # Fetch all pending bills to show in the dropdown
        query_all_bills = """SELECT * FROM bills where status=%s"""
        cursor.execute(query_all_bills,('Pending',))
        all_pending_bills = cursor.fetchall()



        cursor.execute("SELECT ROUND(COALESCE(SUM(balance), 0.00), 2) AS total_balance FROM accounts")

        total_balance = cursor.fetchone()['total_balance']

        if total_balance is None:
            total_balance = 0  
            total_balance = round(total_balance, 2)
        cursor.execute("""
        SELECT id, goal_name, ROUND(goal_target,2) as goal_target, LEAST(100, (100 * %s / goal_target)) AS progress_percentage 
        FROM goals""",(total_balance,))
    
        goals = cursor.fetchall()
        last_goal = goals[-1] if goals else None
        goal_achieved = False
        if last_goal and total_balance >= last_goal['goal_target']:
            goal_achieved = True


        notification_count = len(pending_bills)

            # Prepare data for the template
        return render_template('dashboard.html',username=username, 
                               accounts=accounts, 
                               transactions=transactions,
                               bills=all_bills,due_today=due_today,
                               pending_bills=pending_bills,paid_bills=paid_bills,
                               goals=goals,
                              total_balance=total_balance,
                              expenses=expenses,current_date=current_date,notification_count=notification_count, goal_achieved=goal_achieved,
                               goal_name=last_goal['goal_name'] if goal_achieved else '')
    return redirect(url_for('login'))

# Fetch Accounts from DB
def fetch_accounts():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM accounts")
    accounts = cursor.fetchall()
    cursor.close()
    connection.close()
    return accounts

# Fetch Bills from DB
def fetch_bills():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bills")
    bills = cursor.fetchall()
    cursor.close()
    connection.close()
    return bills

# Fetch Transactions from DB
def fetch_transactions():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM transactions")
    transactions = cursor.fetchall()
    cursor.close()
    connection.close()
    return transactions

# Fetch Daily Data for Charts
def fetch_daily_data():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT DATE(date) AS date,
               SUM(CASE WHEN transaction_type = 'deposit' THEN amount ELSE 0 END) AS deposits,
               SUM(CASE WHEN transaction_type = 'withdrawal' THEN amount ELSE 0 END) AS withdrawals
        FROM transactions
        GROUP BY DATE(date)
        ORDER BY DATE(date) DESC LIMIT 7
    """)
    data = cursor.fetchall()
    cursor.close()
    connection.close()

    dates = [item['date'] for item in data]
    deposits = [item['deposits'] for item in data]
    withdrawals = [item['withdrawals'] for item in data]
    return {'dates': dates, 'deposits': deposits, 'withdrawals': withdrawals}



# Add Account Route
@app.route('/add_account', methods=['POST'])
def add_account():
    if 'loggedin' in session:
        name = request.form['name']
        balance = request.form['balance']
        expdate=request.form['expdate']
        cvv=request.form['cvv']
        cardnumber=request.form['cardnumber']
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("INSERT INTO accounts (name, balance,expdate,cvv,cardno) VALUES (%s, %s,%s,%s,%s)", (name, balance,expdate,cvv,cardnumber))
        connection.commit()
        cursor.close()
        connection.close()

        flash("Account added successfully!")
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Route to add a transaction (deposit/withdrawal)
@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        transaction_type = request.form.get('transaction_type')
        amount = Decimal(request.form.get('amount'))
        transaction_date = request.form.get('date')
        transitem=request.form.get('transitem')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Ensure that results are returned as dictionaries

        # Fetch the current balance of the account
        cursor.execute("SELECT balance, id FROM accounts WHERE id = %s", (account_id,))
        account = cursor.fetchone()

        if not account:
            flash("Account not found.")
            return redirect(url_for('dashboard'))

        current_balance = Decimal(account['balance'])  # Access balance using dictionary key

        # Check for withdrawal condition
        if transaction_type == 'withdrawal' and amount > current_balance:
            flash("Insufficient balance for withdrawal!")
            return redirect(url_for('dashboard'))

        # Initialize new_balance
        new_balance = current_balance  # Set initial value

        # Update the account balance based on transaction type
        if transaction_type == 'deposit':
            new_balance = current_balance + amount
        elif transaction_type == 'withdrawal':
            new_balance = current_balance - amount

        # Ensure new_balance is properly set
        if new_balance is None:
            flash("Invalid transaction type!")
            return redirect(url_for('dashboard'))

        # Update the balance in the accounts table
        cursor.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new_balance, account_id))

        # Insert transaction into transactions table
        cursor.execute("""
            INSERT INTO transactions (account_id,transitem, transaction_type, amount, date)
            VALUES (%s, %s, %s,%s, %s)
        """, (account_id,transitem, transaction_type, amount, transaction_date))

        conn.commit()
        conn.close()

        flash(f"Transaction successful! New balance: {new_balance}")
        return redirect(url_for('dashboard'))
# Add Bill Route
@app.route('/add_bill', methods=['POST'])
def add_bill():
    if 'loggedin' in session:
        bill_name = request.form.get('bill_name')
        item_description = request.form.get('item_description')
        due_date = request.form.get('due_date')
        amount = request.form.get('Billam')

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO bills (bill_name, item_description, due_date, amount,status)
            VALUES (%s, %s, %s, %s,%s)
        """, (bill_name, item_description, due_date, amount,'Pending'))
        connection.commit()
        cursor.close()
        connection.close()

        flash("Bill added successfully!")
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))
@app.route('/add_goal', methods=['POST'])
def add_goal():
    goal_name = request.form['goal_name']
    goal_target = request.form['goal_target']
    
    

    connection = get_db_connection()
    cur= connection.cursor()
    cur.execute("""
        INSERT INTO goals (goal_name, goal_target) 
        VALUES (%s, %s)  -- account_id is no longer relevant
    """, (goal_name, goal_target))
    connection.commit()
    cur.close()

    
    flash("Goal added successfully!")
    return redirect(url_for('dashboard'))


# Delete a goal
@app.route('/delete_goal/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("DELETE FROM goals WHERE id = %s", [goal_id])
    connection.commit()
    cur.close()

    return redirect(url_for('dashboard'))

@app.route('/update_status/<int:bill_id>', methods=['POST'])
def update_status(bill_id):
    if 'loggedin' in session:
        new_status = request.form['status']  # Get the selected status ('Paid' or 'Pending')

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE bills
            SET status = %s
            WHERE id = %s
        """, (new_status, bill_id))
        connection.commit()
        cursor.close()
        connection.close()

        flash(f"Bill status updated to {new_status}!")
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/delete_bill/<int:bill_id>', methods=['POST'])
def delete_bill(bill_id):
    if 'loggedin' in session:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM bills WHERE id = %s", (bill_id,))
        connection.commit()
        cursor.close()
        connection.close()

        flash("Bill deleted successfully!")
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

def fetch_expense():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

        # Query to aggregate amounts by transaction item (transitem)
    cursor.execute("""
        SELECT 
            COALESCE(transitem, 'Unknown') AS transitem,  -- Replace NULL with 'Unknown'
            SUM(amount) AS total_amount
        FROM transactions
        GROUP BY transitem
    """)
        
    expenses_data = cursor.fetchall()
    cursor.close()
    connection.close()

        # Ensure that expenses_data is not empty
    if not expenses_data:
        return render_template('dashboard.html', expenses=[])

        # Prepare the data for the pie chart
    expenses = []
    colors = ['#FF6347', '#FF8C00', '#FFD700', '#ADFF2F', '#00BFFF', '#8A2BE2', '#FF1493', '#32CD32', '#7B68EE']
        
        # Adding data to a list of dictionaries
    for i, expense in enumerate(expenses_data):
        expenses.append({
            'label': expense['transitem'],
            'amount': float(expense['total_amount']),
            'color': colors[i % len(colors)]  # Loop through colors if there are more labels than colors
        })

    return expenses
    
@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('userid', None)
    session.pop('name', None)
    session.pop('email', None)
    flash("You have been logged out successfully.")
    return redirect(url_for('login'))  # Redirect to login page after logging out


# Run the application
if __name__ == '__main__':
    app.run(debug=True)
