/* eglformats.c — dump MESA dma-buf import formats/modifiers per GPU, v2.
 * Changes vs. previous version:
 *   - prints GL_RENDERER / GL_VENDOR / GL_VERSION per run (device identity)
 *   - flags SGRBG-family presence in-loop and prints a per-device verdict
 * Build:
 *   gcc -Wall -O2 eglformats.c -o eglformats \
 *       $(pkg-config --cflags --libs egl glesv2) \
 *   || gcc -Wall -O2 eglformats.c -o eglformats -lEGL -lGLESv2
 */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <stdio.h>
#include <stdlib.h>

#define FOURCC(a,b,c,d) ((unsigned)((a) | ((b) << 8) | ((c) << 16) | ((unsigned)(d) << 24)))

int main(void)
{
    PFNEGLGETPLATFORMDISPLAYEXTPROC get_disp =
        (PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
    if (!get_disp) { fprintf(stderr, "eglGetPlatformDisplayEXT unavailable\n"); return 1; }

    EGLDisplay dpy = get_disp(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    if (dpy == EGL_NO_DISPLAY || !eglInitialize(dpy, NULL, NULL)) {
        fprintf(stderr, "eglInitialize failed (0x%x)\n", eglGetError());
        return 1;
    }

    eglBindAPI(EGL_OPENGL_ES_API);
    EGLConfig cfg; EGLint ncfg = 0;
    const EGLint cfg_attr[] = { EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_NONE };
    if (!eglChooseConfig(dpy, cfg_attr, &cfg, 1, &ncfg) || ncfg < 1) {
        fprintf(stderr, "eglChooseConfig failed (0x%x)\n", eglGetError());
        return 1;
    }

    const EGLint ctx_attr[] = { EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE };
    EGLContext ctx = eglCreateContext(dpy, cfg, EGL_NO_CONTEXT, ctx_attr);
    if (ctx == EGL_NO_CONTEXT ||
        !eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx)) {
        fprintf(stderr, "context/current failed (0x%x)\n", eglGetError());
        return 1;
    }

    printf("  VENDOR   : %s\n", (const char *)glGetString(GL_VENDOR));
    printf("  RENDERER : %s\n", (const char *)glGetString(GL_RENDERER));
    printf("  VERSION  : %s\n", (const char *)glGetString(GL_VERSION));

    PFNEGLQUERYDMABUFFORMATSEXTPROC q_f =
        (PFNEGLQUERYDMABUFFORMATSEXTPROC)eglGetProcAddress("eglQueryDmaBufFormatsEXT");
    PFNEGLQUERYDMABUFMODIFIERSEXTPROC q_m =
        (PFNEGLQUERYDMABUFMODIFIERSEXTPROC)eglGetProcAddress("eglQueryDmaBufModifiersEXT");
    if (!q_f) { fprintf(stderr, "eglQueryDmaBufFormatsEXT not available\n"); return 1; }

    EGLint nf = 0;
    if (!q_f(dpy, 0, NULL, &nf) || nf == 0) {
        fprintf(stderr, "query returned 0 formats\n");
        return 1;
    }
    EGLint *fmts = calloc(nf, sizeof *fmts);
    q_f(dpy, nf, fmts, &nf);

    printf("DRI_PRIME=%s : %d importable dmabuf formats\n",
           getenv("DRI_PRIME") ? getenv("DRI_PRIME") : "unset", nf);

    int found_sgrbg = 0;
    for (EGLint i = 0; i < nf; i++) {
        unsigned f = (unsigned)fmts[i];
        EGLint nm = 0;
        if (q_m) q_m(dpy, fmts[i], 0, NULL, NULL, &nm);
        int is_sgrbg = (f == FOURCC('S','G','R','B'));
        if (is_sgrbg) found_sgrbg = 1;
        printf("  %c%c%c%c  (%d modifiers)%s\n",
               f & 0xff, (f >> 8) & 0xff, (f >> 16) & 0xff, (f >> 24) & 0xff,
               nm, is_sgrbg ? "   <== SGRBG-family PRESENT" : "");
    }

    printf("\nVerdict: SGRBG %s in the import list for this device.\n",
           found_sgrbg
               ? "PRESENT -> EGL import of BA10 possible (unlikely)"
               : "NOT PRESENT -> EGL import of BA10 impossible on this GPU");
    return 0;
}
