# First, specify the base Docker image.
# You can see the Docker images from Apify at https://hub.docker.com/r/apify/.
# You can also use any other image from Docker Hub.
FROM apify/actor-python-selenium

# Second, copy just requirements.txt into the actor image,
# since it should be the only file that affects the dependency install in the next step,
# in order to speed up the build
COPY requirements.txt ./

# Install required utilities
RUN apt-get update && apt-get install -y wget

# Download and install mitmproxy
RUN wget https://downloads.mitmproxy.org/10.0.0/mitmproxy-10.0.0-linux.tar.gz \
    && tar xvzf mitmproxy-10.0.0-linux.tar.gz -C /usr/local/bin/ \
    && rm mitmproxy-10.0.0-linux.tar.gz

# Install the packages specified in requirements.txt,
# Print the installed Python version, pip version
# and all installed packages with their versions for debugging
RUN echo "Python version:" \
 && python --version \
 && echo "Pip version:" \
 && pip --version \
 && echo "Installing dependencies:" \
 && pip install -r requirements.txt \
 && echo "All installed Python packages:" \
 && pip freeze

# Next, copy the remaining files and directories with the source code.
# Since we do this after installing the dependencies, quick build will be really fast
# for most source file changes.
COPY . ./

# Specify how to launch the source code of your actor.
# By default, the "python3 -m src" command is run
CMD ["python3", "-m", "src"]

RUN python3 ./src/webdriver_install.py