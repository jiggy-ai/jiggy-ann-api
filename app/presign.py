import logging
import boto3
import os
from botocore.exceptions import ClientError


linode_obj_config = {
    "aws_access_key_id": os.environ['LINODE_STORAGE_KEY_ID'],
    "aws_secret_access_key": os.environ['LINODE_STORAGE_SECRET_KEY'],
    "endpoint_url": "https://us-southeast-1.linodeobjects.com"}


s3_client = boto3.client('s3', **linode_obj_config)



def create_presigned_url(object_name, expiration=300):
    """Generate a presigned URL to share an S3 object

    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': "jiggy-assets",
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response
