rm -rf submit/agent
mkdir -p submit/agent
cp -a $1/*.py submit/agent
cd submit
zip -r agent.zip agent
cd ..

