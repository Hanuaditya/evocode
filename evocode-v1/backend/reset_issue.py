import sqlite3
conn = sqlite3.connect('evocode.db')
c = conn.cursor()
c.execute("UPDATE issue_reports SET status='failed', current_step=NULL, error_message='Reset: test subprocess was hanging. Click Retry.' WHERE id=4")
conn.commit()
print('Done - Feature #4 reset to failed state')
conn.close()
