# docker build -t kdd - < Dockerfile
# docker run -it -p 3000:3000 -v $PWD:/starter-kit kdd bash

FROM citybrainchallenge/cbengine:0.1.2
RUN apt-get update
RUN apt-get install -y gnupg
RUN curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add -
RUN echo "deb https://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list
RUN apt-get update
RUN apt-get install -y yarn mc vim
