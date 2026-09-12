/* rawsend - write a file straight to the EX-word's bulk endpoint.
 *
 * The stock firmware speaks OBEX (see libexword); OS-update mode does not —
 * it accepts data on bulk-out and stalls bulk-in. This sends raw bytes so we
 * can find out what the updater does with them. The device's own screen is
 * the only feedback channel.
 *
 *   cc rawsend.c -o rawsend $(pkg-config --cflags --libs libusb-1.0)
 *   ./rawsend <file> [endpoint-out] [chunk]
 *
 * DANGEROUS: writing to a firmware updater with no known-good image and no
 * flash backup can brick the device permanently.
 */
#include <stdio.h>
#include <stdlib.h>
#include <libusb.h>

#define VID 0x07cf
#define PID 0x6101

int main(int argc, char **argv)
{
	const char *path = argc > 1 ? argv[1] : NULL;
	unsigned char ep_out = argc > 2 ? (unsigned char)strtol(argv[2], NULL, 0) : 0x01;
	int chunk = argc > 3 ? atoi(argv[3]) : 4096;
	libusb_context *ctx = NULL;
	libusb_device_handle *h;
	unsigned char *buf, in[64];
	long len;
	int rc, sent = 0, total = 0;
	FILE *f;

	if (!path) { fprintf(stderr, "usage: %s <file> [ep-out] [chunk]\n", argv[0]); return 2; }
	if (!(f = fopen(path, "rb"))) { perror(path); return 2; }
	fseek(f, 0, SEEK_END); len = ftell(f); rewind(f);
	if (!(buf = malloc(len)) || fread(buf, 1, len, f) != (size_t)len) { perror("read"); return 2; }
	fclose(f);

	if ((rc = libusb_init(&ctx))) { fprintf(stderr, "init: %s\n", libusb_error_name(rc)); return 1; }
	if (!(h = libusb_open_device_with_vid_pid(ctx, VID, PID))) {
		fprintf(stderr, "device %04x:%04x not found (is it on the bus?)\n", VID, PID);
		libusb_exit(ctx); return 1;
	}
	libusb_set_auto_detach_kernel_driver(h, 1);
	if ((rc = libusb_claim_interface(h, 0))) {
		fprintf(stderr, "claim: %s\n", libusb_error_name(rc));
		libusb_close(h); libusb_exit(ctx); return 1;
	}

	printf("sending %ld bytes to endpoint 0x%02x in %d-byte chunks\n", len, ep_out, chunk);
	while (total < len) {
		int n = (len - total) < chunk ? (int)(len - total) : chunk;
		rc = libusb_bulk_transfer(h, ep_out, buf + total, n, &sent, 5000);
		printf("  offset %6d: rc=%s sent=%d\n", total, libusb_error_name(rc), sent);
		if (rc) break;
		total += sent;
	}
	printf("total written: %d of %ld\n", total, len);

	/* Did feeding it data make the updater talk back? */
	rc = libusb_bulk_transfer(h, 0x82, in, sizeof(in), &sent, 2000);
	printf("read-back on 0x82: rc=%s len=%d\n", libusb_error_name(rc), rc ? 0 : sent);
	for (int i = 0; !rc && i < sent; i++) printf("%02X ", in[i]);
	if (!rc && sent) printf("\n");

	libusb_release_interface(h, 0);
	libusb_close(h);
	libusb_exit(ctx);
	return 0;
}
