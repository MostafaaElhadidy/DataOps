FROM bitnami/spark:3.5.3
USER root
RUN pip install --no-cache-dir pyspark==3.5.3
COPY streaming_job.py /app/streaming_job.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
USER 1001
ENTRYPOINT ["/entrypoint.sh"]
