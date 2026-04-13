import torch
import time


class FindUnusedColor:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "min_distance": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "step": 1,
                        "display": "slider",
                    },
                ),
                "sample_size": (
                    "INT",
                    {
                        "default": 5000,
                        "min": 1000,
                        "max": 50000,
                        "step": 1000,
                        "display": "slider",
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING", "INT", "INT", "INT")
    RETURN_NAMES = ("hex_color", "R", "G", "B")
    FUNCTION = "find_unused_color"
    CATEGORY = "SBTools/Image"
    OUTPUT_NODE = False

    def find_unused_color(self, image, min_distance, sample_size):
        t0 = time.time()
        # ComfyUI image tensor format: (B, H, W, C) with values 0.0-1.0
        # Get first batch RGB 3 channels and convert to 0-255
        img_255 = (image[0, :, :, :3] * 255).round().clamp(0, 255).to(torch.uint8)
        print(f"[DEBUG] Image conversion: {time.time() - t0:.3f}s")

        t1 = time.time()
        # Random sampling from all pixels (avoiding unique operation)
        pixels = img_255.reshape(-1, 3)
        total_pixels = pixels.shape[0]

        # Adjust sample size (use all pixels if sample_size exceeds total)
        actual_sample_size = min(sample_size, total_pixels)

        # Generate random indices and sample
        indices = torch.randperm(total_pixels, device=pixels.device)[
            :actual_sample_size
        ]
        sampled_pixels = pixels[indices].float()

        print(
            f"[DEBUG] Sampling: {time.time() - t1:.3f}s, samples: {actual_sample_size}/{total_pixels}"
        )

        # Common pure color candidates for chroma key/SAM3
        candidates = torch.tensor(
            [
                [0, 255, 0],  # Pure green (green screen)
                [255, 0, 255],  # Magenta
                [0, 0, 255],  # Pure blue (blue screen)
                [0, 255, 255],  # Cyan
                [255, 255, 0],  # Yellow
                [255, 0, 0],  # Pure red
            ],
            dtype=torch.float32,
            device=sampled_pixels.device,
        )

        t2 = time.time()
        best_candidate = None
        best_min_distance = -1

        for candidate in candidates:
            # Calculate distance between candidate color and sampled pixels (Euclidean distance)
            # distance = sqrt((R1-R2)^2 + (G1-G2)^2 + (B1-B2)^2)
            distances = torch.sqrt(((sampled_pixels - candidate) ** 2).sum(dim=1))
            min_dist = distances.min().item()

            print(
                f"[DEBUG] {tuple(candidate.int().tolist())}: min_distance={min_dist:.1f}"
            )

            # Accept if min_distance >= threshold and is the best so far
            if min_dist >= min_distance and min_dist > best_min_distance:
                best_min_distance = min_dist
                best_candidate = candidate

        print(f"[DEBUG] Distance calculation: {time.time() - t2:.3f}s")

        unused = None
        if best_candidate is not None:
            unused = tuple(best_candidate.int().tolist())
            print(f"[DEBUG] Selected: {unused}, min_distance={best_min_distance:.1f}")

        # Coarse search if no candidate color found
        if unused is None:
            print(
                "[DEBUG] No candidate color meets the criteria. Starting coarse search..."
            )
            t3 = time.time()

            step = 17  # 0, 17, 34, ..., 255 (16 steps)
            for r in range(0, 256, step):
                for g in range(0, 256, step):
                    for b in range(0, 256, step):
                        test_color = torch.tensor(
                            [r, g, b], dtype=torch.float32, device=sampled_pixels.device
                        )
                        distances = torch.sqrt(
                            ((sampled_pixels - test_color) ** 2).sum(dim=1)
                        )
                        min_dist = distances.min().item()

                        if min_dist >= min_distance and min_dist > best_min_distance:
                            best_min_distance = min_dist
                            unused = (r, g, b)

            print(f"[DEBUG] Coarse search: {time.time() - t3:.3f}s")

        # Fallback if still not found (theoretically should not happen)
        if unused is None:
            unused = (128, 128, 128)

        r, g, b = unused
        hex_color = f"#{r:02x}{g:02x}{b:02x}"

        print(f"[DEBUG] Total time: {time.time() - t0:.3f}s")
        return (hex_color, r, g, b)


NODE_CLASS_MAPPINGS = {"FindUnusedColor": FindUnusedColor}

NODE_DISPLAY_NAME_MAPPINGS = {"FindUnusedColor": "Find Unused Color"}
