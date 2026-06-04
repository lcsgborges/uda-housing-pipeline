from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from app.pipelines.airflow_tasks import (
    airflow_extraction_batch_task,
    airflow_ingestion_task,
)

default_args = {
    "owner": "uda-pipeline",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="uda_housing_pipeline",
    default_args=default_args,
    description="Ingestao de RI + extracao semantica em batch",
    schedule_interval="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["uda", "housing", "llm", "rustfs"],
) as dag:
    ingest_task = PythonOperator(
        task_id="ingest_new_documents",
        python_callable=airflow_ingestion_task,
    )

    extract_batch_task = PythonOperator(
        task_id="extract_metrics_batch",
        python_callable=airflow_extraction_batch_task,
        op_kwargs={"batch_size": 10},
    )

    ingest_task >> extract_batch_task
