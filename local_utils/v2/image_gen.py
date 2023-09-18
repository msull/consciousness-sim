from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
from logzero import logger

from local_utils.settings import StreamlitAppSettings


def generate_image(prompt: str) -> bytes:
    # Your PAT (Personal Access Token) can be found in the portal under Authentification
    settings = StreamlitAppSettings.load()
    # Specify the correct user_id/app_id pairings
    # Since you're making inferences outside your app's scope
    USER_ID = "stability-ai"
    APP_ID = "stable-diffusion-2"
    # Change these to whatever model and text URL you want to use
    MODEL_ID = "stable-diffusion-xl"

    channel = ClarifaiChannel.get_grpc_channel()
    stub = service_pb2_grpc.V2Stub(channel)

    metadata = (("authorization", "Key " + settings.clarifai_pat.get_secret_value()),)

    userDataObject = resources_pb2.UserAppIDSet(user_id=USER_ID, app_id=APP_ID)

    # To use a local text file, uncomment the following lines
    # with open(TEXT_FILE_LOCATION, "rb") as f:
    #    file_bytes = f.read()

    logger.debug("GENERATING IMAGE")
    logger.debug(prompt)

    post_model_outputs_response = stub.PostModelOutputs(
        service_pb2.PostModelOutputsRequest(
            user_app_id=userDataObject,
            model_id=MODEL_ID,
            inputs=[
                resources_pb2.Input(
                    data=resources_pb2.Data(
                        text=resources_pb2.Text(
                            raw=prompt
                            # url=TEXT_FILE_URL
                            # raw=file_bytes
                        )
                    )
                )
            ],
        ),
        metadata=metadata,
    )
    if post_model_outputs_response.status.code != status_code_pb2.SUCCESS:
        print(post_model_outputs_response.status)
        raise Exception("Post model outputs failed, status: " + post_model_outputs_response.status.description)

    # Since we have one input, one output will exist here
    image = post_model_outputs_response.outputs[0].data.image.base64
    return image
