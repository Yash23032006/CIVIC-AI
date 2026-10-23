
document.addEventListener("DOMContentLoaded", () => {
    const issueForm = document.getElementById("issueForm");

    if (!issueForm) {
        console.error("CivicAI: issueForm was not found.");
        return;
    }

    const problemInput = document.getElementById("problem");
    const languageSelect = document.getElementById("language");
    const locationInput = document.getElementById("location");

    // Optional photo and GPS controls
    const photoInput = document.getElementById("evidencePhotos");
    const photoPreview = document.getElementById("photoPreview");
    const captureGpsButton = document.getElementById("captureGps");
    const clearGpsButton = document.getElementById("clearGps");
    const gpsStatus = document.getElementById("gpsStatus");
    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");
    const gpsAccuracyInput = document.getElementById("gpsAccuracy");

    // =========================================================
    // 1. MULTILINGUAL VOICE INPUT: ENGLISH, HINDI, MARATHI
    // =========================================================

    const micButton = document.getElementById("micButton");
    const micStatus = document.getElementById("micStatus");

    if (problemInput && languageSelect && micButton) {
        const SpeechRecognition =
            window.SpeechRecognition ||
            window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            micButton.disabled = true;

            if (micStatus) {
                micStatus.textContent =
                    "Voice input is not supported by this browser. Try Chrome.";
            }
        } else {
            const recognition = new SpeechRecognition();

            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;

            const languageCodes = {
                English: "en-IN",
                Hindi: "hi-IN",
                Marathi: "mr-IN"
            };

            let listening = false;
            let manuallyStopped = false;
            let finalTranscript = "";
            let originalText = "";
            let micErrorOccurred = false;

            function updateLanguage() {
                recognition.lang =
                    languageCodes[languageSelect.value] || "en-IN";
            }

            languageSelect.addEventListener("change", () => {
                if (listening) {
                    if (micStatus) {
                        micStatus.textContent =
                            "Stop recording before changing the language.";
                    }
                    return;
                }

                updateLanguage();

                if (micStatus) {
                    micStatus.textContent =
                        "Ready to listen in " + languageSelect.value + ".";
                }
            });

            micButton.addEventListener("click", () => {
                if (listening) {
                    manuallyStopped = true;
                    recognition.stop();
                    return;
                }

                updateLanguage();

                manuallyStopped = false;
                micErrorOccurred = false;
                finalTranscript = "";
                originalText = problemInput.value.trim();

                try {
                    recognition.start();
                } catch (error) {
                    console.error("Microphone start error:", error);

                    if (micStatus) {
                        micStatus.textContent =
                            "Could not start the microphone. Please try again.";
                    }
                }
            });

            recognition.onstart = () => {
                listening = true;
                micButton.textContent = "⏹️";
                micButton.setAttribute("aria-label", "Stop voice input");

                if (micStatus) {
                    micStatus.textContent =
                        "Listening in " + languageSelect.value +
                        ". Speak clearly, then tap stop.";
                }
            };

            recognition.onresult = (event) => {
                let interimTranscript = "";

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;

                    if (event.results[i].isFinal) {
                        finalTranscript += transcript + " ";
                    } else {
                        interimTranscript += transcript;
                    }
                }

                const newSpeech =
                    (finalTranscript + interimTranscript).trim();

                problemInput.value = [
                    originalText,
                    newSpeech
                ].filter(Boolean).join(originalText ? " " : "");

                problemInput.dispatchEvent(
                    new Event("input", { bubbles: true })
                );
            };

            recognition.onerror = (event) => {
                micErrorOccurred = true;

                const messages = {
                    "not-allowed":
                        "Microphone access denied. Allow it in browser settings.",
                    "service-not-allowed":
                        "Speech recognition service is blocked by the browser.",
                    "no-speech":
                        "No speech detected. Try speaking again.",
                    "audio-capture":
                        "No microphone detected. Check your microphone connection.",
                    "network":
                        "Speech recognition network error. Check your connection.",
                    "aborted":
                        "Voice recording was stopped."
                };

                if (micStatus) {
                    micStatus.textContent =
                        messages[event.error] ||
                        "Voice recognition failed: " + event.error;
                }
            };

            recognition.onend = () => {
                listening = false;
                micButton.textContent = "🎤";
                micButton.setAttribute("aria-label", "Start voice input");

                if (micErrorOccurred) {
                    micErrorOccurred = false;
                    return;
                }

                if (micStatus) {
                    micStatus.textContent = finalTranscript.trim()
                        ? "Voice input captured. Review the text before submitting."
                        : manuallyStopped
                            ? "Recording stopped. No speech was captured."
                            : "Recording ended. Tap the microphone to try again.";
                }

                manuallyStopped = false;
            };

            updateLanguage();
        }
    }

    // =========================================================
    // 2. OPTIONAL PHOTO EVIDENCE
    // =========================================================

    const MAX_PHOTOS = 4;
    const MAX_PHOTO_SIZE = 5 * 1024 * 1024;

    const allowedPhotoTypes = [
        "image/jpeg",
        "image/png",
        "image/webp"
    ];

    function renderPhotoPreview() {
        if (!photoInput || !photoPreview) return;

        photoPreview.replaceChildren();

        Array.from(photoInput.files || []).forEach((file) => {
            const wrapper = document.createElement("div");
            const label = document.createElement("p");

            label.textContent = file.name;
            label.className = "field-help";

            if (allowedPhotoTypes.includes(file.type)) {
                const image = document.createElement("img");
                const objectUrl = URL.createObjectURL(file);

                image.src = objectUrl;
                image.alt = "Selected evidence photo";

                image.onload = () => URL.revokeObjectURL(objectUrl);
                image.onerror = () => URL.revokeObjectURL(objectUrl);

                wrapper.appendChild(image);
            }

            wrapper.appendChild(label);
            photoPreview.appendChild(wrapper);
        });
    }

    if (photoInput) {
        photoInput.addEventListener("change", () => {
            const files = Array.from(photoInput.files || []);

            if (files.length > MAX_PHOTOS) {
                alert("You can attach a maximum of 4 photos.");
                photoInput.value = "";
                renderPhotoPreview();
                return;
            }

            const invalidFile = files.find((file) =>
                !allowedPhotoTypes.includes(file.type) ||
                file.size > MAX_PHOTO_SIZE ||
                file.size === 0
            );

            if (invalidFile) {
                alert(
                    "Each photo must be a non-empty JPEG, PNG, or WebP image " +
                    "no larger than 5 MB."
                );

                photoInput.value = "";
                renderPhotoPreview();
                return;
            }

            renderPhotoPreview();
        });
    }

    // =========================================================
    // 3. OPTIONAL GPS LOCATION
    // =========================================================

    if (captureGpsButton) {
        captureGpsButton.addEventListener("click", () => {
            if (!navigator.geolocation) {
                if (gpsStatus) {
                    gpsStatus.textContent =
                        "GPS is not supported by this browser. Enter your location manually.";
                }
                return;
            }

            captureGpsButton.disabled = true;

            if (gpsStatus) {
                gpsStatus.textContent =
                    "Requesting your location permission...";
            }

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    if (latitudeInput) {
                        latitudeInput.value = position.coords.latitude;
                    }

                    if (longitudeInput) {
                        longitudeInput.value = position.coords.longitude;
                    }

                    if (gpsAccuracyInput) {
                        gpsAccuracyInput.value =
                            position.coords.accuracy ?? "";
                    }

                    if (gpsStatus) {
                        gpsStatus.textContent =
                            "GPS captured. Accuracy: approximately " +
                            Math.round(position.coords.accuracy) + " metres.";
                    }

                    captureGpsButton.disabled = false;
                },
                (error) => {
                    const messages = {
                        1: "Location permission denied. You can still enter the location manually.",
                        2: "Current location is unavailable. Try again or enter it manually.",
                        3: "Location request timed out. Please try again."
                    };

                    if (gpsStatus) {
                        gpsStatus.textContent =
                            messages[error.code] ||
                            "Unable to capture GPS. Enter the location manually.";
                    }

                    captureGpsButton.disabled = false;
                },
                {
                    enableHighAccuracy: true,
                    timeout: 15000,
                    maximumAge: 0
                }
            );
        });
    }

    if (clearGpsButton) {
        clearGpsButton.addEventListener("click", () => {
            if (latitudeInput) latitudeInput.value = "";
            if (longitudeInput) longitudeInput.value = "";
            if (gpsAccuracyInput) gpsAccuracyInput.value = "";

            if (gpsStatus) {
                gpsStatus.textContent =
                    "GPS cleared. You can still enter your location manually.";
            }
        });
    }

    // =========================================================
    // 4. SUBMIT REPORT, PHOTOS AND GPS
    // =========================================================

    issueForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const problem = problemInput.value.trim();
        const language = languageSelect.value;
        const location = locationInput.value.trim();

        if (!problem || !location) {
            alert("Please enter the problem description and location.");
            return;
        }

        const citizenEmail = sessionStorage.getItem("userEmail");

        if (!citizenEmail) {
            alert("Please login before submitting a civic issue.");
            window.location.href = "login.html";
            return;
        }

        const photos = Array.from(photoInput?.files || []);

        if (photos.length > MAX_PHOTOS) {
            alert("You can attach a maximum of 4 photos.");
            return;
        }

        const invalidPhoto = photos.find((file) =>
            !allowedPhotoTypes.includes(file.type) ||
            file.size === 0 ||
            file.size > MAX_PHOTO_SIZE
        );

        if (invalidPhoto) {
            alert("Please select valid JPEG, PNG, or WebP photos, up to 5 MB each.");
            return;
        }

        const submitButton = issueForm.querySelector(
            'button[type="submit"], input[type="submit"]'
        );

        if (submitButton) submitButton.disabled = true;

        try {
            const formData = new FormData();

            formData.append("problem", problem);
            formData.append("language", language);
            formData.append("location", location);
            formData.append("citizen_email", citizenEmail);

            if (latitudeInput?.value && longitudeInput?.value) {
                formData.append("latitude", latitudeInput.value);
                formData.append("longitude", longitudeInput.value);

                if (gpsAccuracyInput?.value) {
                    formData.append("gps_accuracy_m", gpsAccuracyInput.value);
                }
            }

            photos.forEach((photo) => {
                formData.append("evidence_photos", photo);
            });

            const response = await fetch("/api/report", {
                method: "POST",
                body: formData
            });

            const responseText = await response.text();
            let result;

            try {
                result = JSON.parse(responseText);
            } catch (parseError) {
                console.error("Invalid JSON response:", responseText);

                alert(
                    "CivicAI server returned an unexpected response.\n\n" +
                    "HTTP Status: " + response.status + "\n\n" +
                    responseText.substring(0, 500)
                );
                return;
            }

            if (!response.ok) {
                if (
                    response.status === 409 &&
                    result.code === "DUPLICATE_REPORT"
                ) {
                    const similarity = Number(result.similarity_score);

                    const similarityText = Number.isFinite(similarity)
                        ? "\nSimilarity: " + similarity + "%"
                        : "";

                    alert(
                        "⚠️ Possible Duplicate Complaint\n\n" +
                        (result.message || "A similar report already exists.") +
                        "\nExisting Report ID: " +
                        (result.existing_report_id || "Unavailable") +
                        "\nCurrent Status: " +
                        (result.existing_status || "Unknown") +
                        similarityText +
                        (result.matched_problem
                            ? "\n\nExisting complaint: " + result.matched_problem
                            : "")
                    );

                    return;
                }

                alert(
                    "Failed to submit civic issue.\n\n" +
                    (result.message || "Unknown server error")
                );
                return;
            }

            alert(
                "Civic issue submitted successfully!\n\n" +
                "Report ID: " + result.id + "\n" +
                "AI Category: " + result.category + "\n" +
                "AI Severity: " + result.severity + "\n" +
                "Location: " + result.location + "\n" +
                "AI Priority Score: " + result.priority_score + "/100" +
                (result.evidence_count !== undefined
                    ? "\nPhotos uploaded: " + result.evidence_count
                    : "") +
                (result.latitude != null && result.longitude != null
                    ? "\nGPS coordinates captured."
                    : "\nGPS coordinates not provided.")
            );

            issueForm.reset();

            if (photoPreview) photoPreview.replaceChildren();

            if (gpsStatus) {
                gpsStatus.textContent =
                    "GPS not captured. You can still enter your location manually.";
            }

        } catch (error) {
            console.error("Report submission error:", error);

            alert(
                "Unable to submit the report. Please check your connection " +
                "and try again."
            );
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });
});