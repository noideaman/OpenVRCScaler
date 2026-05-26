# OpenVRCScaler

The goal of this project is to create a simple desktop tool that enables OSC-based avatar scaling in VRChat using VRChat's OSC scaling parameters.

The official VRChat documentation for this can be found here: https://docs.vrchat.com/docs/osc-avatar-scaling

## Tech Stack

* Python (using `python-osc`)
* Tkinter (for a lightweight desktop UI)

## VRChat Scaling Parameters

These are all prefixed by `/avatar/`

* **eyeheight**
    * The current height of the avatar in meters.
    * Read this for the current height.
    * Write this to set a new height.
* **eyeheightscalingallowed**
    * Tells us whether avatar scaling is disallowed by the current VRChat world. When false, `eyeheight` updates should be ignored.

## Menu Control Parameters

These are all prefixed by `/avatar/parameters/`. VRChat radial menus output float values from `0.00` to `1.00`.

* **OpenVRCScaler_ScalingEnabled**
    * Type: Boolean
    * Description: Enables or disables scaling. If false, ignore all input to other scaling options.
* **OpenVRCScaler_TransistionTime**
    * Type: Float (0.00 - 1.00)
    * Description: The duration of the scaling transition in seconds. Must be multiplied by 100.
    * Example: `0.00` is instant. `0.05` is 5 seconds.
* **OpenVRCScaler_Hundreds**
    * Type: Float (0.00 - 1.00)
    * Description: Dictates the macro scale up to 10,000 meters. 
    * Formula: `(value * 100) * 100` (e.g., `0.35` equals 3,500 meters).
* **OpenVRCScaler_Ones**
    * Type: Float (0.00 - 1.00)
    * Description: Dictates the tens and ones scale up to 100 meters.
    * Formula: `value * 100` (e.g., `0.45` equals 45 meters).
* **OpenVRCScaler_Decimal**
    * Type: Float (0.00 - 1.00)
    * Description: Dictates the decimal scale up to 1 meter.
    * Formula: `value * 1` (e.g., `0.35` equals 0.35 meters).

## Core Functionality & Math

1.  **Target Height Calculation:** The user will open their in-game radial menu and change options. The app must read these parameters, calculate the target height by summing the three position parameters together, and send the updated `eyeheight` to VRChat via OSC.
2.  **Smooth Transitions:** Because instant transitions don't look great, the transition time parameter dictates how long it takes to scale from the old height to the new height. Update the height smoothly over this duration (e.g., using a 50ms interval loop).
3.  **Dynamic Transition Updates:** If a user changes their scale while already in the process of a transition, **do not restart the transition timer**. Simply calculate the new distance and speed up/slow down the scaling interval to reach the new target scale in whatever time is remaining.
4.  **Reverse Decomposition (External Changes):** If the user's height is changed by external means (e.g., forced by a VRChat world) and not by our active transition, we must update the radial menu to reflect this. Break the new height down into the three `0.00` to `1.00` floats for Hundreds, Ones, and Decimals, and send them back to VRChat via OSC so the user's menu matches their new height.
5.  **Bounds & Clamping:** VRChat's max scaling height is 10,000 meters. If the user tries to exceed this by combining parameters (e.g., Hundreds maxed out, plus added Ones), clamp the target height to 10,000. Immediately reverse-decompose this 10,000m cap and send the corrected values back to their radial menu (Hundreds to `1.00`, Ones to `0.00`, Decimal to `0.00`). Set a hard minimum floor of `0.1` meters to prevent breaking the avatar.

## UI Requirements

The Tkinter UI should be simple and display the following:
* The OSC connection state (e.g., listening on port 9001).
* The current height of the user.
* The current state/value of all five menu settings.
* A **"Reset Height to 1m"** button that sets the user's height to 1 meter and updates their radial menu parameters to match.
* A clickable link at the bottom to the project's GitHub repo: `https://github.com/SkyeCA/VRChatOscScaler`