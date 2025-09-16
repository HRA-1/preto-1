import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AWSAuthError(Exception):
    """AWS 인증 관련 커스텀 예외"""
    pass

class AWSCredentialsNotFoundError(AWSAuthError):
    """AWS 인증정보를 찾을 수 없을 때의 예외"""
    pass

class AWSCredentialsInvalidError(AWSAuthError):
    """AWS 인증정보가 유효하지 않을 때의 예외"""
    pass

def load_aws_credentials():
    """
    .env 파일에서 AWS 인증정보를 로드합니다.

    Returns:
        dict: AWS 인증정보 딕셔너리

    Raises:
        AWSCredentialsNotFoundError: 필수 인증정보가 없을 때
    """
    load_dotenv()

    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_default_region = os.getenv('AWS_DEFAULT_REGION', 'ap-northeast-2')

    if not aws_access_key_id or not aws_secret_access_key:
        raise AWSCredentialsNotFoundError(
            "AWS_ACCESS_KEY_ID와 AWS_SECRET_ACCESS_KEY가 .env 파일에 설정되어 있지 않습니다."
        )

    return {
        'aws_access_key_id': aws_access_key_id,
        'aws_secret_access_key': aws_secret_access_key,
        'region_name': aws_default_region
    }

def get_aws_session(**kwargs):
    """
    AWS 세션 객체를 생성합니다.

    Args:
        **kwargs: 추가 세션 파라미터

    Returns:
        boto3.Session: AWS 세션 객체

    Raises:
        AWSCredentialsNotFoundError: 인증정보가 없을 때
    """
    try:
        credentials = load_aws_credentials()
        credentials.update(kwargs)

        session = boto3.Session(**credentials)
        logger.info(f"AWS 세션이 생성되었습니다. 리전: {credentials['region_name']}")
        return session

    except Exception as e:
        logger.error(f"AWS 세션 생성 중 오류 발생: {str(e)}")
        raise

def get_aws_client(service_name, **kwargs):
    """
    특정 AWS 서비스의 클라이언트를 생성합니다.

    Args:
        service_name (str): AWS 서비스 이름 (예: 's3', 'ec2', 'rds')
        **kwargs: 추가 클라이언트 파라미터

    Returns:
        boto3 client: 지정된 서비스의 클라이언트

    Raises:
        AWSCredentialsNotFoundError: 인증정보가 없을 때
        AWSCredentialsInvalidError: 인증정보가 유효하지 않을 때
    """
    try:
        session = get_aws_session()
        client = session.client(service_name, **kwargs)
        logger.info(f"{service_name.upper()} 클라이언트가 생성되었습니다.")
        return client

    except (NoCredentialsError, PartialCredentialsError) as e:
        logger.error(f"AWS 인증정보 오류: {str(e)}")
        raise AWSCredentialsInvalidError(f"AWS 인증정보가 유효하지 않습니다: {str(e)}")
    except Exception as e:
        logger.error(f"AWS 클라이언트 생성 중 오류 발생: {str(e)}")
        raise

def get_aws_resource(service_name, **kwargs):
    """
    특정 AWS 서비스의 리소스를 생성합니다.

    Args:
        service_name (str): AWS 서비스 이름 (예: 's3', 'ec2', 'dynamodb')
        **kwargs: 추가 리소스 파라미터

    Returns:
        boto3 resource: 지정된 서비스의 리소스

    Raises:
        AWSCredentialsNotFoundError: 인증정보가 없을 때
        AWSCredentialsInvalidError: 인증정보가 유효하지 않을 때
    """
    try:
        session = get_aws_session()
        resource = session.resource(service_name, **kwargs)
        logger.info(f"{service_name.upper()} 리소스가 생성되었습니다.")
        return resource

    except (NoCredentialsError, PartialCredentialsError) as e:
        logger.error(f"AWS 인증정보 오류: {str(e)}")
        raise AWSCredentialsInvalidError(f"AWS 인증정보가 유효하지 않습니다: {str(e)}")
    except Exception as e:
        logger.error(f"AWS 리소스 생성 중 오류 발생: {str(e)}")
        raise

def validate_credentials():
    """
    현재 AWS 인증정보의 유효성을 검증합니다.

    Returns:
        dict: 검증 결과 및 계정 정보

    Raises:
        AWSCredentialsInvalidError: 인증정보가 유효하지 않을 때
    """
    try:
        sts_client = get_aws_client('sts')

        # 현재 인증정보로 계정 정보 조회
        response = sts_client.get_caller_identity()

        result = {
            'valid': True,
            'account_id': response.get('Account'),
            'user_arn': response.get('Arn'),
            'user_id': response.get('UserId')
        }

        logger.info(f"AWS 인증정보 검증 성공. 계정 ID: {result['account_id']}")
        return result

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"AWS 인증정보 검증 실패: {error_code} - {error_message}")
        raise AWSCredentialsInvalidError(f"인증정보 검증 실패: {error_message}")
    except Exception as e:
        logger.error(f"인증정보 검증 중 예상치 못한 오류: {str(e)}")
        raise

def get_available_regions(service_name='ec2'):
    """
    지정된 서비스에서 사용 가능한 리전 목록을 반환합니다.

    Args:
        service_name (str): AWS 서비스 이름 (기본값: 'ec2')

    Returns:
        list: 사용 가능한 리전 목록
    """
    try:
        session = get_aws_session()
        return session.get_available_regions(service_name)
    except Exception as e:
        logger.error(f"리전 목록 조회 중 오류 발생: {str(e)}")
        return []

def test_connection():
    """
    AWS 연결을 테스트합니다.

    Returns:
        bool: 연결 성공 여부
    """
    try:
        validate_credentials()
        logger.info("AWS 연결 테스트 성공")
        return True
    except Exception as e:
        logger.error(f"AWS 연결 테스트 실패: {str(e)}")
        return False

# 편의 함수들
def get_s3_client(**kwargs):
    """S3 클라이언트 생성"""
    return get_aws_client('s3', **kwargs)

def get_ec2_client(**kwargs):
    """EC2 클라이언트 생성"""
    return get_aws_client('ec2', **kwargs)

def get_rds_client(**kwargs):
    """RDS 클라이언트 생성"""
    return get_aws_client('rds', **kwargs)

def get_lambda_client(**kwargs):
    """Lambda 클라이언트 생성"""
    return get_aws_client('lambda', **kwargs)

def get_dynamodb_resource(**kwargs):
    """DynamoDB 리소스 생성"""
    return get_aws_resource('dynamodb', **kwargs)