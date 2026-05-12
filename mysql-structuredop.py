#pip install langchain langchain-community langchain-openai pymysql sqlalchemy

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain.chains import create_sql_query_chain
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List

# 1. Connect to your MySQL Database
# Format: mysql+pymysql://user:password@host/dbname
db = SQLDatabase.from_uri("mysql+pymysql://root:password@localhost/my_database")

# 2. Define your desired structured output format
class EmployeeInfo(BaseModel):
    name: str = Field(description="Full name of the employee")
    department: str = Field(description="Department name")
    salary: float = Field(description="Annual salary")

class EmployeeList(BaseModel):
    employees: List[EmployeeInfo]

# 3. Initialize the LLM with structured output capability
llm = ChatOpenAI(model="gpt-4o", temperature=0)
structured_llm = llm.with_structured_output(EmployeeList)

# 4. Create the SQL Query Chain
# This chain converts natural language to a MySQL query
query_chain = create_sql_query_chain(llm, db)

# 5. Execute and Structure
user_question = "List the top 3 highest paid employees and their departments"

# Step A: Generate the SQL query
sql_query = query_chain.invoke({"question": user_question})

# Step B: Execute query on MySQL
raw_data = db.run(sql_query)

# Step C: Use the LLM to map the raw data into the structured schema
# We provide the raw SQL output as context
prompt = f"Format the following database result into the required structure: {raw_data}"
structured_response = structured_llm.invoke(prompt)

print(structured_response.employees)
