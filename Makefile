IMAGE_NAME := bess-bc

.PHONY: build run test validate shell clean

build:
	docker build -t $(IMAGE_NAME) .

run:
	docker run --rm -v "$$(pwd)":/data -w /data $(IMAGE_NAME) $(ARGS)

test:
	docker run --rm -v "$$(pwd)":/app -w /app --entrypoint pytest $(IMAGE_NAME) tests/ -v

validate:
	docker run --rm -v "$$(pwd)":/app -w /app --entrypoint python3 $(IMAGE_NAME) scripts/validate_against_excel.py

shell:
	docker run --rm -it -v "$$(pwd)":/data -w /data --entrypoint bash $(IMAGE_NAME)


clean:
	docker rmi $(IMAGE_NAME) 2>/dev/null || true
