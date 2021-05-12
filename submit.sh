mkdir -p submit
rm -r submit/agent
cp -a $1 submit/agent
cd submit
zip -r agent.zip agent
cd ..

