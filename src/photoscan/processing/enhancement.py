
import cv2
import numpy as np

from photoscan.domain.models import ScanMode, ScanSettings


def sauvola_threshold(gray: np.ndarray, window_size: int = 25, k: float = 0.2, r_val: float = 128.0) -> np.ndarray:
    """
    Applies Sauvola adaptive thresholding.
    Formula: T = m * (1 + k * (s / r_val - 1))
    Where m is the local mean, s is the local standard deviation, and r_val is the dynamic range of std.
    """
    if window_size % 2 == 0:
        window_size += 1
    window_size = max(3, window_size)

    gray_f = gray.astype(np.float32)
    mean = cv2.boxFilter(gray_f, -1, (window_size, window_size))
    sq_mean = cv2.boxFilter(gray_f ** 2, -1, (window_size, window_size))

    # Calculate standard deviation safely
    variance = sq_mean - (mean ** 2)
    variance = np.clip(variance, 0, None)
    std = np.sqrt(variance)

    thresh = mean * (1.0 + k * (std / r_val - 1.0))
    binary = np.where(gray_f > thresh, 255, 0).astype(np.uint8)
    return binary

class DocumentEnhancer:
    """
    Applies configurable scanner-style filters, illumination normalization,
    and thresholding to produce flat, high-contrast, professional document outputs.
    """

    def apply_illumination_correction(self, rgb_image: np.ndarray, settings: ScanSettings) -> np.ndarray:
        """
        Estimates the slowly varying background on the L (luminance) channel in the LAB color space
        and divides the channel by the background to normalize uneven lighting.
        """
        strength = settings.shadow_removal_strength
        if strength <= 0.0:
            return rgb_image.copy()

        # Convert to LAB space
        lab = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        h, w = l_channel.shape
        # Compute dynamic kernel size (approx 15% of max dimension, must be odd)
        kernel_size = int(max(h, w) * 0.15)
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel_size = max(15, kernel_size)

        # Estimate background using morphological closing
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        bg_l = cv2.morphologyEx(l_channel, cv2.MORPH_CLOSE, kernel)

        # Smooth background estimate to avoid harsh transitions
        bg_l = cv2.GaussianBlur(bg_l, (kernel_size, kernel_size), 0)

        # Normalize luminance channel: Division normalization
        # Add epsilon to guard against division by zero
        l_float = l_channel.astype(np.float32)
        bg_float = bg_l.astype(np.float32)

        normalized_l = (l_float / (bg_float + 1e-5)) * 255.0
        normalized_l = np.clip(normalized_l, 0, 255).astype(np.uint8)

        # Blend corrected L with original L based on strength parameter
        final_l = cv2.addWeighted(normalized_l, strength, l_channel, 1.0 - strength, 0)

        # Recombine and convert back to RGB
        merged_lab = cv2.merge([final_l, a_channel, b_channel])
        return cv2.cvtColor(merged_lab, cv2.COLOR_LAB2RGB)

    def classify_page_content(self, rgb_image: np.ndarray) -> ScanMode:
        """
        Analyzes the page content (colorfulness, edge patterns) to automatically
        choose an appropriate scan mode.
        """
        # Convert to LAB to inspect the colorfulness (A and B channels)
        lab = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2LAB)
        _, a, b = cv2.split(lab)

        # Compute standard deviation of chromaticity channels
        color_std = np.std(a.astype(np.float32)) + np.std(b.astype(np.float32))

        # Low color variance implies a black/white or grayscale document
        if color_std < 12.0:
            return ScanMode.GRAYSCALE
        return ScanMode.COLOR

    def apply_denoising_and_sharpening(self, rgb_image: np.ndarray, settings: ScanSettings) -> np.ndarray:
        """
        Applies fast bilateral/Gaussian denoising and high-quality unsharp mask sharpening.
        """
        img = rgb_image.copy()

        # Denoising
        if settings.denoising_strength > 0.0:
            # Scale filter parameters based on strength
            d = int(settings.denoising_strength * 10) + 3
            sc = settings.denoising_strength * 50
            ss = settings.denoising_strength * 50
            img = cv2.bilateralFilter(img, d, sc, ss)

        # Sharpening (Unsharp Masking)
        if settings.sharpening_amount > 0.0:
            # Blend sharp edge map back to image
            blurred = cv2.GaussianBlur(img, (5, 5), 1.0)
            high_pass = cv2.subtract(img, blurred)
            img = cv2.addWeighted(img, 1.0, high_pass, settings.sharpening_amount, 0)

        return img

    def enhance(self, rgb_image: np.ndarray, settings: ScanSettings) -> np.ndarray:
        """
        Processes a cropped, rectified document image under the given settings and mode.
        """
        mode = settings.mode
        if mode == ScanMode.AUTO:
            mode = self.classify_page_content(rgb_image)

        # 1. Apply basic global adjustments (brightness, contrast, saturation)
        # Apply contrast and brightness offset
        adjusted = rgb_image.astype(np.float32)
        adjusted = (adjusted - 128.0) * settings.contrast + 128.0 + (settings.brightness * 255.0)
        adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)

        # Apply Saturation adjustment
        if settings.saturation != 1.0:
            hsv = cv2.cvtColor(adjusted, cv2.COLOR_RGB2HSV).astype(np.float32)
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * settings.saturation, 0, 255)
            adjusted = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

        # 2. Apply Mode Specific pipeline
        if mode == ScanMode.ORIGINAL_ENHANCED:
            # Only mild illumination correction + denoising/sharpening
            img = self.apply_illumination_correction(adjusted, settings)
            return self.apply_denoising_and_sharpening(img, settings)

        elif mode == ScanMode.COLOR:
            # Full illumination correction, mild cleanup, and sharpening
            img = self.apply_illumination_correction(adjusted, settings)
            img = self.apply_denoising_and_sharpening(img, settings)
            return img

        elif mode == ScanMode.GRAYSCALE:
            # Illumination correction, then gray conversion and local contrast control
            img = self.apply_illumination_correction(adjusted, settings)
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            # Enhance local contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_gray = clahe.apply(gray)

            enhanced_gray = self.apply_denoising_and_sharpening(cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2RGB), settings)
            return enhanced_gray

        elif mode == ScanMode.BLACK_WHITE:
            # Apply Sauvola thresholding
            gray = cv2.cvtColor(adjusted, cv2.COLOR_RGB2GRAY)
            # Convert UI bias (slider) to float parameter 'k'
            k = settings.threshold_bias / 100.0 if settings.threshold_bias != 0 else 0.2
            binary = sauvola_threshold(gray, window_size=settings.adaptive_threshold_window_size, k=k)
            # Convert binary to RGB output representation
            return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)

        elif mode == ScanMode.RECEIPT:
            # Receipts need maximum contrast, high adaptive thresholding, and clean margins
            gray = cv2.cvtColor(adjusted, cv2.COLOR_RGB2GRAY)
            # Sauvola with smaller window size and higher k
            binary = sauvola_threshold(gray, window_size=15, k=0.1)
            return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)

        elif mode == ScanMode.PHOTO:
            # Preserves embedded illustrations, applies conservative illumination correction
            settings_copy = settings.model_copy(update={"shadow_removal_strength": settings.shadow_removal_strength * 0.5})
            img = self.apply_illumination_correction(adjusted, settings_copy)
            return self.apply_denoising_and_sharpening(img, settings)

        return adjusted
